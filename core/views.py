import base64
import io
import json
import numpy as np
import face_recognition
import secrets

from django.contrib.auth import logout
from django.templatetags.static import static
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from PIL import Image
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from attendance.models import AttendanceLog
from .forms import InquiryForm
from django.utils import timezone
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.forms import CustomUserSimpleForm
from users.models import CustomUser


User = get_user_model()


def _get_face_encoding_from_base64(data_url: str):
    """از Base64 خروجی بایت می‌گیرد و بردار چهره (128 بعدی) را برمی‌گرداند."""
    try:
        if not data_url or ',' not in data_url:
            return None
        _, b64data = data_url.split(",", 1)
        img_bytes = base64.b64decode(b64data)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        encs = face_recognition.face_encodings(
            np.array(img), num_jitters=5, model="large"
        )
        return encs[0] if encs else None
    except Exception as e:
        print("Face encode error:", e)
        return None


# —————————————————————————
# کلاس‌های ورود
# —————————————————————————

class ManagementLoginView(LoginView):
    template_name = "core/management_login.html"
    redirect_authenticated_user = True
    def get_success_url(self):
        # پس از ورود با رمز، می‌فرستیم برای تأیید چهره مدیریت
        return reverse("management_face_check")


class DeviceLoginView(LoginView):
    template_name = "core/device_login.html"
    redirect_authenticated_user = False
    def form_valid(self, form):
        user = form.get_user()
        if not user.is_staff:
            form.add_error(None, "دسترسی ندارید")
            return self.form_invalid(form)
        login(self.request, user)
        return redirect("device_face_check")


# —————————————————————————
# صفحات عمومی
# —————————————————————————

def home(request):
    return render(request, "core/home.html")


# —————————————————————————
# بخش دستگاه (کیوسک)
# —————————————————————————

@login_required
@user_passes_test(lambda u: u.is_staff)
def device_face_check(request):
    if request.user.face_encoding is None:
        return render(request, "core/register_face.html")
    return render(request, "core/device_face_check.html")


@login_required
def device_page(request):
    """صفحهٔ اصلی کیوسک برای ثبت تردد کاربران عادی"""
    return render(request, "core/device.html")


@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def api_device_verify_face(request):
    """
    API تشخیص چهره مدیر برای فعال‌سازی کیوسک
    """
    try:
        data = json.loads(request.body)
        enc = _get_face_encoding_from_base64(data.get("image", ""))
        if enc is None:
            return JsonResponse({"success": False, "error": "چهره یافت نشد."})

        if request.user.face_encoding is None:
            return JsonResponse({"success": False, "error": "چهره مدیر ثبت نشده."})

        known = np.frombuffer(request.user.face_encoding, dtype=np.float64)
        distance = np.linalg.norm(known - enc)
        if distance < 0.5:
            return JsonResponse({"success": True, "redirect": reverse("device_page")})
        else:
            return JsonResponse({"success": False, "error": "تشخیص ناموفق."})

    except Exception:
        return JsonResponse({"success": False, "error": "خطا در پردازش تصویر."})

@csrf_exempt
@require_POST
@login_required
def api_verify_face(request):
    try:
        data = json.loads(request.body)
        enc = _get_face_encoding_from_base64(data.get("image", ""))
        if enc is None:
            return JsonResponse({"ok": False, "msg": "چهره واضح نیست."})

        for u in User.objects.exclude(face_encoding__isnull=True):
            known = np.frombuffer(u.face_encoding, dtype=np.float64)
            if np.linalg.norm(known - enc) < 0.5:
                if u.is_staff:
                    return JsonResponse({"ok": False, "manager_detected": True})
                # ثبت تردد کاربر عادی
                AttendanceLog.objects.create(user=u, timestamp=timezone.now())
                img_url = u.face_image.url if hasattr(u, 'face_image') and u.face_image else static('core/avatar.png')
                return JsonResponse({
                    "ok": True,
                    "name": f"{u.first_name} {u.last_name}",
                    "code": u.personnel_code,
                    "timestamp": timezone.now().isoformat(),
                    "image_url": img_url
                })
        return JsonResponse({"ok": False, "msg": "شناسایی ناموفق."})
    except Exception:
        return JsonResponse({"ok": False, "msg": "خطا در پردازش تصویر."})

@require_POST
@login_required
def api_register_face(request):
    data_url = request.POST.get("image", "")
    enc = _get_face_encoding_from_base64(data_url)
    if enc is None:
        return JsonResponse({"ok": False, "msg": "چهره‌ای شناسایی نشد."})

    # ۱) ذخیرهٔ بردار چهره
    request.user.face_encoding = enc.tobytes()

    # ۲) ذخیرهٔ تصویر خام
    try:
        header, b64data = data_url.split(",", 1)
        fmt = header.split(";")[0].split("/")[1]  # مثال: 'png' یا 'jpeg'
        img_data = base64.b64decode(b64data)
        filename = f"{request.user.username}_face.{fmt}"
        request.user.face_image.save(filename, ContentFile(img_data), save=False)
    except Exception:
        pass

    request.user.save()
    return JsonResponse({"ok": True, "redirect": reverse("management_dashboard")})
# —————————————————————————
# مشاهده تردد کاربر عادی
# —————————————————————————

def user_inquiry(request):
    if request.method == "POST":
        form = InquiryForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                u = User.objects.get(
                    personnel_code=cd["personnel_code"],
                    national_id=cd["national_id"]
                )
            except User.DoesNotExist:
                form.add_error(None, "اطلاعات معتبر نیست")
            else:
                request.session["inquiry_user_id"] = u.id
                return redirect("my_logs")
    else:
        form = InquiryForm()
    return render(request, "core/user_inquiry.html", {"form": form})


@login_required
def my_logs(request):
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    logs = AttendanceLog.objects.filter(user=u).order_by("-timestamp")
    return render(request, "attendance/my_logs.html", {"user": u, "logs": logs})


# —————————————————————————
# پنل مدیریت کاربران
# —————————————————————————

staff_required = user_passes_test(lambda u: u.is_staff)

@login_required
@staff_required
def management_face_check(request):
    """برای مدیریت، ثبت/تأیید چهره و سپس دسترسی به پنل"""
    if request.user.face_encoding is None:
        return render(request, "core/register_face.html")
    return render(request, "core/management_face_check.html")


@csrf_exempt
@login_required
@staff_required
def api_management_verify_face(request):
    import base64
    import face_recognition

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            image_data = data.get("image")
            if not image_data:
                return JsonResponse({"success": False, "error": "عکس ارسال نشده."})
            # decode image
            image_b64 = image_data.split(",")[1]
            img_bytes = base64.b64decode(image_b64)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            import cv2
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            encs = face_recognition.face_encodings(img)
            if not encs:
                return JsonResponse({"success": False, "error": "چهره‌ای شناسایی نشد."})
            enc = encs[0]
            known = np.frombuffer(request.user.face_encoding, dtype=np.float64)
            distance = np.linalg.norm(known - enc)
            if distance < 0.5:
                # چهره تایید شد! مجوز ورود بده
                request.session["face_verified"] = True
                return JsonResponse({"success": True})
            else:
                return JsonResponse({"success": False, "error": "چهره مطابقت نداشت."})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"خطا: {e}"})
    return JsonResponse({"success": False, "error": "درخواست نامعتبر."})


@login_required
@staff_required
def management_users(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    users = User.objects.all()
    return render(request, "core/management_users.html", {"users": users})


@login_required
@staff_required
def user_add(request):
    if request.method == "POST":
        form = CustomUserSimpleForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            # ست پسورد تصادفی قوی (غیرقابل حدس)
            user.set_password(secrets.token_urlsafe(16))
            user.save()
            messages.success(request, "کاربر جدید اضافه شد.")
            return redirect("register_face_page_for_user", user_id=user.pk)
    else:
        form = CustomUserSimpleForm()
    return render(request, "core/user_form.html", {"form": form, "title": "افزودن کاربر جدید"})

@login_required
@staff_required
def user_update(request, pk):
    obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = CustomUserSimpleForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "کاربر ویرایش شد.")
            return redirect("management_users")
    else:
        form = CustomUserSimpleForm(instance=obj)
    return render(request, "core/user_form.html", {"form": form, "title": "ویرایش کاربر"})

@login_required
@staff_required
def user_delete(request, pk):
    obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if obj == request.user:
            messages.error(request, "نمی‌توانید خودتان را حذف کنید.")
        else:
            obj.delete()
            messages.success(request, "حذف موفق.")
        return redirect("management_users")
    return render(request, "core/user_confirm_delete.html", {"user": obj})

@login_required
@staff_required
def register_face_page_for_user(request, user_id):
    target = get_object_or_404(User, id=user_id)
    return render(request, "core/register_face_for_user.html", {"user_to_register": target})


@require_POST
@login_required
@staff_required
def register_face_api(request, user_id):
    target = get_object_or_404(User, id=user_id)
    data_url = request.POST.get("image", "")
    enc = _get_face_encoding_from_base64(data_url)
    if enc is None:
        return JsonResponse({"ok": False, "msg": "چهره‌ای شناسایی نشد."})

    target.face_encoding = enc.tobytes()
    # ذخیره عکس خام
    try:
        header, b64data = data_url.split(",", 1)
        fmt = header.split(";")[0].split("/")[1]
        img_data = base64.b64decode(b64data)
        filename = f"{target.username}_face.{fmt}"
        target.face_image.save(filename, ContentFile(img_data), save=False)
    except Exception:
        pass

    target.save()
    return JsonResponse({"ok": True})


# ======= گزارش‌گیری پیشرفته =======
@login_required
@staff_required
def management_dashboard(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    # آمار کلی
    total_users = User.objects.count()
    today_logs = AttendanceLog.objects.filter(timestamp__date=timezone.now().date()).count()
    users_without_face = User.objects.filter(face_encoding__isnull=True).count()

    # نمودار تردد 7 روز اخیر
    date_range = [timezone.now().date() - timedelta(days=i) for i in range(6, -1, -1)]
    daily_logs = []
    for date in date_range:
        logs = AttendanceLog.objects.filter(timestamp__date=date).count()
        daily_logs.append(logs)

    context = {
        'active_tab': 'dashboard',
        'total_users': total_users,
        'today_logs': today_logs,
        'users_without_face': users_without_face,
        'date_range': [d.strftime("%Y-%m-%d") for d in date_range],
        'daily_logs': daily_logs
    }
    return render(request, 'core/management_dashboard.html', context)


# ======= گزارش‌گیری کاربران =======
@login_required
@staff_required
def user_reports(request):
    # محاسبات آماری
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    users_with_face = User.objects.filter(face_encoding__isnull=False).count()

    # آخرین ترددها
    latest_logs = AttendanceLog.objects.select_related('user').order_by('-timestamp')[:10]

    context = {
        'active_tab': 'reports',
        'active_users': active_users,
        'inactive_users': inactive_users,
        'users_with_face': users_with_face,
        'latest_logs': latest_logs
    }
    return render(request, 'core/user_reports.html', context)


def custom_logout(request):
    logout(request)
    request.session.flush()
    return redirect("home")
