import base64
import io
import json
import secrets
from datetime import timedelta, datetime, time

import face_recognition
import numpy as np
from PIL import Image
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.core.files.base import ContentFile
from django.http import JsonResponse
import jdatetime
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from attendance.models import AttendanceLog, SuspiciousLog, EditRequest, LeaveRequest, WeeklyHoliday
from core.forms import (
    CustomUserSimpleForm,
    InquiryForm,
    EditRequestForm,
    LeaveRequestForm,
    ManualLeaveForm,
    AttendanceStatusForm,
    UserLogsRangeForm,
    UserRangeForm,
    WeeklyHolidayForm,
    AttendanceDeviceForm,
    WorkShiftForm,
    CompanyPolicyForm,
    WorkGroupForm,
    WorkUnitForm,
    RequestTypeForm,
)
from users.models import CustomUser
from core.models import (
    AttendanceDevice, WorkShift, CompanyPolicy, WorkGroup, WorkUnit, RequestType
)


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
        best_user = None
        best_dist = float("inf")

        for u in User.objects.exclude(face_encoding__isnull=True):
            known = np.frombuffer(u.face_encoding, dtype=np.float64)
            dist = np.linalg.norm(known - enc)
            if dist < best_dist:
                best_dist = dist
                best_user = u
            if dist < 0.5:
                if u.is_staff:
                    return JsonResponse({"ok": False, "manager_detected": True})
                last_log = AttendanceLog.objects.filter(user=u).order_by('-timestamp').first()
                if last_log and timezone.now() - last_log.timestamp < timedelta(minutes=5):
                    return JsonResponse({"ok": False, "msg": "تردد تکراری"})

                today = timezone.now().date()
                if last_log and last_log.log_type == 'in' and last_log.timestamp.date() < today:
                    end_of_day = datetime.combine(last_log.timestamp.date(), time(23, 59))
                    if settings.USE_TZ:
                        end_of_day = timezone.make_aware(end_of_day)
                    AttendanceLog.objects.create(user=u, timestamp=end_of_day, log_type='out', source='auto')

                log_type = 'out' if last_log and last_log.log_type == 'in' else 'in'
                AttendanceLog.objects.create(user=u, timestamp=timezone.now(), log_type=log_type, source='self')
                img_url = u.face_image.url if hasattr(u, 'face_image') and u.face_image else static('core/avatar.png')
                return JsonResponse({
                    "ok": True,
                    "name": f"{u.first_name} {u.last_name}",
                    "code": u.personnel_code,
                    "timestamp": timezone.now().isoformat(),
                    "log_type": log_type,
                    "image_url": img_url
                })

        if best_user and best_dist < 0.6:
            # log suspicious attempt for admin review
            try:
                header, b64data = data.get("image", "").split(",", 1)
                fmt = header.split(";")[0].split("/")[1]
                img_data = base64.b64decode(b64data)
                filename = f"suspect_{timezone.now().timestamp()}.{fmt}"
                log = SuspiciousLog.objects.create(
                    matched_user=best_user,
                    similarity=best_dist,
                )
                log.image.save(filename, ContentFile(img_data), save=True)
            except Exception:
                SuspiciousLog.objects.create(matched_user=best_user, similarity=best_dist)
            return JsonResponse({"ok": False, "suspicious": True})

        return JsonResponse({"ok": False, "msg": "شناسایی ناموفق."})
    except Exception:
        return JsonResponse({"ok": False, "msg": "خطا در پردازش تصویر."})

@require_POST
@login_required
def api_register_face(request):
    """ثبت چهرهٔ کاربر با بررسی حرکت ساده برای جلوگیری از تقلب."""
    img1 = request.POST.get("image1")
    img2 = request.POST.get("image2")
    if img1 and img2:
        enc1 = _get_face_encoding_from_base64(img1)
        enc2 = _get_face_encoding_from_base64(img2)
        if enc1 is None or enc2 is None:
            return JsonResponse({"ok": False, "msg": "چهره واضح نیست."})
        # تفاوت دو تصویر باید از حدی بیشتر باشد تا اطمینان پیدا کنیم عکس ثابت نیست
        movement = np.linalg.norm(enc1 - enc2)
        if movement < 0.08:
            return JsonResponse({"ok": False, "msg": "حرکت تشخیص داده نشد."})
        enc = (enc1 + enc2) / 2
        data_url = img1
    else:
        # حالت قدیمی، بدون لایونس
        data_url = request.POST.get("image", "")
        enc = _get_face_encoding_from_base64(data_url)
        if enc is None:
            return JsonResponse({"ok": False, "msg": "چهره‌ای شناسایی نشد."})

    request.user.face_encoding = enc.tobytes()

    # ذخیرهٔ تصویر خام
    try:
        header, b64data = data_url.split(",", 1)
        fmt = header.split(";")[0].split("/")[1]
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
                return redirect("user_profile")
    else:
        form = InquiryForm()
    return render(request, "core/user_inquiry.html", {"form": form})


def user_profile(request):
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    return render(request, "core/user_profile.html", {"user": u})


def my_logs(request):
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    month = request.GET.get("month")
    if month:
        jy, jm = [int(x) for x in month.split("-")]
    else:
        today_j = jdatetime.date.today()
        jy, jm = today_j.year, today_j.month
    days = jdatetime.j_days_in_month[jm - 1]
    start_g = jdatetime.date(jy, jm, 1).togregorian()
    end_g = jdatetime.date(jy, jm, days).togregorian()
    qs = AttendanceLog.objects.filter(user=u, timestamp__date__range=(start_g, end_g)).order_by("timestamp")
    daily = {d: {"in": None, "out": None} for d in range(1, days + 1)}
    for log in qs:
        jd = jdatetime.date.fromgregorian(date=log.timestamp.date())
        info = daily.get(jd.day)
        if log.log_type == "in" and info["in"] is None:
            info["in"] = log.timestamp.time()
        if log.log_type == "out":
            info["out"] = log.timestamp.time()
    prev_month_date = (jdatetime.date(jy, jm, 1) - jdatetime.timedelta(days=1))
    next_month_date = (jdatetime.date(jy, jm, days) + jdatetime.timedelta(days=1))
    context = {
        "user": u,
        "daily_logs": daily,
        "jyear": jy,
        "jmonth": jm,
        "prev_month": f"{prev_month_date.year}-{prev_month_date.month:02d}",
        "next_month": f"{next_month_date.year}-{next_month_date.month:02d}",
    }
    return render(request, "attendance/my_logs.html", context)


def export_my_logs_csv(request):
    """Export current user's logs stored in session as CSV"""
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    logs = AttendanceLog.objects.filter(user=u).order_by("-timestamp")
    import csv
    from django.http import HttpResponse
    import jdatetime

    response = HttpResponse(content_type='text/csv')
    filename = f"{u.personnel_code}_logs.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['تاریخ', 'ساعت', 'نوع', 'ثبت‌کننده'])
    for log in logs:
        jd = jdatetime.datetime.fromgregorian(datetime=log.timestamp)
        writer.writerow([
            jd.strftime('%Y/%m/%d'),
            jd.strftime('%H:%M:%S'),
            'ورود' if log.log_type == 'in' else 'خروج',
            'کاربر' if log.source == 'self' else ('سیستم' if log.source == 'auto' else 'مدیر'),
        ])
    return response


def edit_request(request):
    """Allow a user to request adding a missing attendance log."""
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    if request.method == "POST":
        form = EditRequestForm(request.POST, user=u)
        if form.is_valid():
            obj = form.save(commit=False)
            ts = obj.timestamp
            if settings.USE_TZ:
                if timezone.is_naive(ts):
                    ts = timezone.make_aware(ts)
            else:
                if timezone.is_aware(ts):
                    ts = timezone.make_naive(ts)
            obj.timestamp = ts
            obj.save()
            messages.success(request, "درخواست شما ثبت شد و در انتظار تأیید است.")
            return redirect("my_logs")
    else:
        form = EditRequestForm(user=u)
    return render(request, "core/edit_request_form.html", {"form": form, "user": u})


def leave_request(request):
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    if request.method == "POST":
        form = LeaveRequestForm(request.POST, user=u)
        if "confirm" in request.POST:
            if form.is_valid():
                obj = form.save(commit=False)
                obj.save()
                messages.success(request, "درخواست مرخصی ثبت شد.")
                return redirect("user_profile")
        else:
            if form.is_valid():
                return render(
                    request,
                    "core/leave_request_confirm.html",
                    {"form": form, "user": u, "end_date": form.cleaned_data["end_jalali"]},
                )
    else:
        form = LeaveRequestForm(user=u)
    return render(request, "core/leave_request_form.html", {"form": form, "user": u})


def user_edit_requests(request):
    """Display current user's edit requests and their status."""
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    requests_qs = EditRequest.objects.filter(user=u).order_by("-created_at")
    return render(request, "core/my_edit_requests.html", {"user": u, "requests": requests_qs})


def cancel_edit_request(request, pk):
    """Allow a user to cancel their pending edit request."""
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    req = get_object_or_404(EditRequest, id=pk, user_id=uid)
    if req.status == "pending":
        req.status = "cancelled"
        req.decision_at = timezone.now()
        req.cancelled_by_user = True
        req.save()
        messages.info(request, "درخواست ویرایش لغو شد.")
    return redirect("user_edit_requests")


def user_leave_requests(request):
    """Display current user's leave requests and their status."""
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    requests_qs = LeaveRequest.objects.filter(user=u).order_by("-created_at")
    return render(request, "core/my_leave_requests.html", {"user": u, "requests": requests_qs})


def cancel_leave_request(request, pk):
    """Allow a user to cancel a pending leave request."""
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    req = get_object_or_404(LeaveRequest, id=pk, user_id=uid)
    if req.status == "pending":
        req.status = "cancelled"
        req.decision_at = timezone.now()
        req.cancelled_by_user = True
        req.save()
        messages.info(request, "درخواست مرخصی لغو شد.")
    return redirect("user_leave_requests")


def my_performance(request):
    """Show current user's working hours in a date range."""
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    u = get_object_or_404(User, id=uid)
    form = UserLogsRangeForm(request.GET or None)
    rows = []
    total_seconds = 0
    if form.is_valid():
        start = form.cleaned_data.get("start_g")
        end = form.cleaned_data.get("end_g")
        if start and end:
            day = start
            while day <= end:
                logs = AttendanceLog.objects.filter(user=u, timestamp__date=day).order_by("timestamp")
                first_in = logs.filter(log_type="in").first()
                last_out = logs.filter(log_type="out").last()
                daily = 0
                if first_in and last_out:
                    daily = (last_out.timestamp - first_in.timestamp).total_seconds()
                rows.append({
                    "date": day,
                    "in": first_in.timestamp.time() if first_in else None,
                    "out": last_out.timestamp.time() if last_out else None,
                    "hours": round(daily / 3600, 2),
                })
                total_seconds += daily
                day += timedelta(days=1)

    return render(request, "core/my_performance.html", {
        "form": form,
        "rows": rows,
        "total_hours": round(total_seconds / 3600, 2),
        "user": u,
    })


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
    img1 = request.POST.get("image1")
    img2 = request.POST.get("image2")
    if img1 and img2:
        enc1 = _get_face_encoding_from_base64(img1)
        enc2 = _get_face_encoding_from_base64(img2)
        if enc1 is None or enc2 is None:
            return JsonResponse({"ok": False, "msg": "چهره واضح نیست."})
        if np.linalg.norm(enc1 - enc2) < 0.08:
            return JsonResponse({"ok": False, "msg": "حرکت تشخیص داده نشد."})
        enc = (enc1 + enc2) / 2
        data_url = img1
    else:
        data_url = request.POST.get("image", "")
        enc = _get_face_encoding_from_base64(data_url)
        if enc is None:
            return JsonResponse({"ok": False, "msg": "چهره‌ای شناسایی نشد."})

    target.face_encoding = enc.tobytes()
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
    today = timezone.now().date()
    is_holiday = WeeklyHoliday.objects.filter(weekday=today.weekday()).exists()
    total_users = User.objects.count()
    today_logs = AttendanceLog.objects.filter(timestamp__date=today).count()
    users_without_face = User.objects.filter(face_encoding__isnull=True).count()

    # لیست کارکنان حاضر، غایب و مرخصی
    if is_holiday:
        present_users = leave_users = absent_users = User.objects.none()
        present_ids = []
    else:
        present_ids = AttendanceLog.objects.filter(timestamp__date=today).values_list('user_id', flat=True).distinct()
        leave_ids = LeaveRequest.objects.filter(start_date__lte=today, end_date__gte=today).values_list('user_id', flat=True).distinct()
        present_users = User.objects.filter(id__in=present_ids)
        leave_users = User.objects.filter(id__in=leave_ids)
        absent_users = User.objects.filter(is_active=True).exclude(id__in=present_ids).exclude(id__in=leave_ids)

    tardy_users = User.objects.none()
    total_hours = 0
    if not is_holiday:
        # محاسبه تاخیر ورود (بعد از ساعت 9)
        tardy_ids = []
        start_time = time(9, 0)
        for uid in present_ids:
            first_log = AttendanceLog.objects.filter(user_id=uid, timestamp__date=today).order_by('timestamp').first()
            if first_log and first_log.timestamp.astimezone(timezone.get_current_timezone()).time() > start_time:
                tardy_ids.append(uid)
        tardy_users = User.objects.filter(id__in=tardy_ids)

        # مجموع ساعات کاری تخمینی (اختلاف اولین و آخرین تردد)
        total_seconds = 0
        for uid in present_ids:
            logs = AttendanceLog.objects.filter(user_id=uid, timestamp__date=today).order_by('timestamp')
            if logs.count() >= 2:
                delta = logs.last().timestamp - logs.first().timestamp
                total_seconds += delta.total_seconds()
        total_hours = round(total_seconds / 3600, 2)

    # هشدارها
    pending_edits = EditRequest.objects.filter(status='pending').count()
    pending_leaves = LeaveRequest.objects.filter(status='pending').count()
    suspicious_today = SuspiciousLog.objects.filter(timestamp__date=today).count()

    # نمودار تردد 7 روز اخیر
    date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]
    daily_logs = []
    for date in date_range:
        logs = AttendanceLog.objects.filter(timestamp__date=date).count()
        daily_logs.append(logs)

    # prepare JSON for chart rendering
    import json
    labels_json = json.dumps([d.strftime('%Y-%m-%d') for d in date_range])
    logs_json = json.dumps(daily_logs)

    context = {
        'active_tab': 'dashboard',
        'total_users': total_users,
        'today_logs': today_logs,
        'users_without_face': users_without_face,
        'present_users': present_users,
        'absent_users': absent_users,
        'leave_users': leave_users,
        'present_count': present_users.count(),
        'absent_count': absent_users.count(),
        'leave_count': leave_users.count(),
        'tardy_users': tardy_users,
        'pending_edits': pending_edits,
        'pending_leaves': pending_leaves,
        'suspicious_today': suspicious_today,
        'total_hours': total_hours,
        'date_range_json': labels_json,
        'daily_logs_json': logs_json,
        'is_holiday': is_holiday,
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
    total_users = User.objects.count()
    users_without_face = total_users - users_with_face

    import json
    status_data_json = json.dumps([active_users, inactive_users])
    face_data_json = json.dumps([users_with_face, users_without_face])

    # آخرین ترددها
    latest_logs = AttendanceLog.objects.select_related('user').order_by('-timestamp')[:10]

    context = {
        'active_tab': 'reports',
        'active_users': active_users,
        'inactive_users': inactive_users,
        'users_with_face': users_with_face,
        'users_without_face': users_without_face,
        'latest_logs': latest_logs,
        'status_data_json': status_data_json,
        'face_data_json': face_data_json,
    }
    return render(request, 'core/user_reports.html', context)


@login_required
@staff_required
def export_logs_csv(request):
    """Download all attendance logs as CSV for admins"""
    logs = AttendanceLog.objects.select_related('user').order_by('-timestamp')
    import csv
    from django.http import HttpResponse
    import jdatetime

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(['کاربر', 'کد پرسنلی', 'تاریخ', 'ساعت', 'نوع', 'ثبت‌کننده'])
    for log in logs:
        jd = jdatetime.datetime.fromgregorian(datetime=log.timestamp)
        writer.writerow([
            log.user.get_full_name(),
            log.user.personnel_code,
            jd.strftime('%Y/%m/%d'),
            jd.strftime('%H:%M:%S'),
            'ورود' if log.log_type == 'in' else 'خروج',
            'کاربر' if log.source == 'self' else ('سیستم' if log.source == 'auto' else 'مدیر'),
        ])
    return response


@login_required
@staff_required
def attendance_status(request):
    """Display attendance status for a given date."""
    if request.GET:
        form = AttendanceStatusForm(request.GET)
    else:
        form = AttendanceStatusForm(initial={'date': jdatetime.date.today()})
    if form.is_valid() and form.cleaned_data.get("date"):
        target_date = form.cleaned_data["date"].togregorian()
    else:
        target_date = timezone.now().date()

    holiday = WeeklyHoliday.objects.filter(weekday=target_date.weekday()).exists()
    if holiday:
        present_users = leave_users = absent_users = User.objects.none()
    else:
        present_ids = AttendanceLog.objects.filter(timestamp__date=target_date).values_list('user_id', flat=True).distinct()
        leave_ids = LeaveRequest.objects.filter(start_date__lte=target_date, end_date__gte=target_date).values_list('user_id', flat=True).distinct()
        present_users = User.objects.filter(id__in=present_ids)
        leave_users = User.objects.filter(id__in=leave_ids)
        absent_users = User.objects.filter(is_active=True).exclude(id__in=present_ids).exclude(id__in=leave_ids)

    jdate = jdatetime.date.fromgregorian(date=target_date)

    context = {
        'active_tab': 'attendance_status',
        'present_users': present_users,
        'absent_users': absent_users,
        'leave_users': leave_users,
        'jdate': jdate.strftime('%Y/%m/%d'),
        'realtime': target_date == timezone.now().date(),
        'form': form,
        'holiday': holiday,
    }
    return render(request, 'core/attendance_status.html', context)


@login_required
@staff_required
def api_attendance_status(request):
    """Return attendance lists as JSON for live updates."""
    form = AttendanceStatusForm(request.GET or None)
    if form.is_valid() and form.cleaned_data.get("date"):
        target_date = form.cleaned_data["date"].togregorian()
    else:
        target_date = timezone.now().date()

    holiday = WeeklyHoliday.objects.filter(weekday=target_date.weekday()).exists()
    if holiday:
        present_users = leave_users = absent_users = []
    else:
        present_ids = AttendanceLog.objects.filter(timestamp__date=target_date).values_list('user_id', flat=True).distinct()
        leave_ids = LeaveRequest.objects.filter(start_date__lte=target_date, end_date__gte=target_date).values_list('user_id', flat=True).distinct()
        present_users = User.objects.filter(id__in=present_ids)
        leave_users = User.objects.filter(id__in=leave_ids)
        absent_users = User.objects.filter(is_active=True).exclude(id__in=present_ids).exclude(id__in=leave_ids)

    data = {
        'present': [{'id': u.id, 'name': u.get_full_name(), 'code': u.personnel_code} for u in present_users],
        'absent': [{'id': u.id, 'name': u.get_full_name(), 'code': u.personnel_code} for u in absent_users],
        'leave': [{'id': u.id, 'name': u.get_full_name(), 'code': u.personnel_code} for u in leave_users],
    }
    return JsonResponse(data)


@login_required
@staff_required
def suspicious_logs(request):
    """List suspicious recognition attempts for admin review."""
    logs = SuspiciousLog.objects.select_related('matched_user').order_by('-timestamp')[:50]
    return render(request, 'core/suspicious_logs.html', {
        'active_tab': 'suspicions',
        'logs': logs,
    })


@login_required
@staff_required
def edit_requests(request):
    """List and process edit requests from users."""
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == "POST":
        req = get_object_or_404(EditRequest, id=request.POST.get("req_id"))
        if req.status == "pending":
            action = request.POST.get("action")
            note = request.POST.get("manager_note", "")
            if action == "approve":
                AttendanceLog.objects.create(
                    user=req.user,
                    timestamp=req.timestamp,
                    log_type=req.log_type,
                    source="manager",
                )
                req.status = "approved"
                req.decision_at = timezone.now()
                req.manager_note = note
                req.save()
                messages.success(request, "درخواست تأیید شد.")
            elif action == "reject":
                req.status = "rejected"
                req.decision_at = timezone.now()
                req.manager_note = note
                req.save()
                messages.info(request, "درخواست رد شد.")
            elif action == "cancel":
                req.status = "cancelled"
                req.decision_at = timezone.now()
                req.manager_note = note
                req.save()
                messages.info(request, "درخواست لغو شد.")
        return redirect("edit_requests")
    requests = EditRequest.objects.select_related("user").filter(cancelled_by_user=False).order_by("-created_at")
    return render(request, "core/edit_requests.html", {
        'active_tab': 'edit_requests',
        'requests': requests,
    })


@login_required
@staff_required
def leave_requests(request):
    """List and process leave requests from users."""
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == "POST":
        req = get_object_or_404(LeaveRequest, id=request.POST.get("req_id"))
        action = request.POST.get("action")
        note = request.POST.get("manager_note", "")
        if action in {"approve", "reject", "cancel"} and req.status == "pending":
            if action == "approve":
                req.status = "approved"
                msg = "درخواست مرخصی تأیید شد."
            elif action == "reject":
                req.status = "rejected"
                msg = "درخواست مرخصی رد شد."
            else:
                req.status = "cancelled"
                msg = "درخواست مرخصی لغو شد."
            req.decision_at = timezone.now()
            req.manager_note = note
            req.save()
            messages.info(request, msg)
        elif action == "update" and req.start_date > timezone.now().date():
            status = request.POST.get("status")
            if status in {"pending", "approved", "rejected", "cancelled"}:
                req.status = status
                req.decision_at = timezone.now() if status != "pending" else None
                req.manager_note = note
                req.save()
                messages.success(request, "وضعیت مرخصی به‌روزرسانی شد.")
        return redirect("leave_requests")
    requests = LeaveRequest.objects.select_related("user").filter(cancelled_by_user=False).order_by("-created_at")
    return render(request, "core/leave_requests.html", {
        'active_tab': 'leave_requests',
        'requests': requests,
        'today': timezone.now().date(),
    })


@login_required
@staff_required
def add_leave(request):
    """Allow admin to manually register a leave for a user."""
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == "POST":
        form = ManualLeaveForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "مرخصی ثبت شد.")
            return redirect("leave_requests")
    else:
        form = ManualLeaveForm()
    return render(request, "core/manual_leave_form.html", {
        'active_tab': 'leave_requests',
        'form': form,
    })


def custom_logout(request):
    logout(request)
    request.session.flush()
    return redirect("home")


@login_required
@staff_required
def weekly_holidays(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    existing = set(WeeklyHoliday.objects.values_list("weekday", flat=True))
    if request.method == "POST":
        form = WeeklyHolidayForm(request.POST)
        if form.is_valid():
            days = [int(d) for d in form.cleaned_data["days"]]
            WeeklyHoliday.objects.all().delete()
            for d in days:
                WeeklyHoliday.objects.create(weekday=d)
            messages.success(request, "روزهای تعطیل ذخیره شد.")
            existing = set(days)
    else:
        form = WeeklyHolidayForm(initial={"days": [str(d) for d in existing]})
    return render(request, "core/weekly_holidays.html", {"form": form, "active_tab": "weekly_holidays"})


@login_required
@staff_required
def user_logs_admin(request, user_id):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    user = get_object_or_404(User, id=user_id)
    form = UserLogsRangeForm(request.GET or None)
    logs = []
    if form.is_valid():
        sd = form.cleaned_data.get("start_g")
        ed = form.cleaned_data.get("end_g")
        if sd and ed:
            logs = AttendanceLog.objects.filter(user=user, timestamp__date__gte=sd, timestamp__date__lte=ed).order_by("timestamp")
    return render(request, "core/user_logs_admin.html", {
        "active_tab": "management_users",
        "user": user,
        "form": form,
        "logs": logs,
    })

@login_required
@staff_required
def manager_cartable(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    edits = EditRequest.objects.filter(status='pending')[:10]
    leaves = LeaveRequest.objects.filter(status='pending')[:10]
    susp = SuspiciousLog.objects.order_by('-timestamp')[:10]
    return render(request, 'core/manager_cartable.html', {
        'pending_edits': edits,
        'pending_leaves': leaves,
        'suspicious_logs': susp,
    })

@login_required
@staff_required
def daily_performance(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    form = AttendanceStatusForm(request.GET or None)
    if form.is_valid() and form.cleaned_data.get("date"):
        target_date = form.cleaned_data["date"].togregorian()
    else:
        target_date = timezone.now().date()

    results = []
    for u in User.objects.all():
        logs = AttendanceLog.objects.filter(user=u, timestamp__date=target_date).order_by("timestamp")
        first_in = logs.filter(log_type="in").first()
        last_out = logs.filter(log_type="out").last()
        hours = 0
        if first_in and last_out:
            hours = round((last_out.timestamp - first_in.timestamp).total_seconds() / 3600, 2)
        results.append({"user": u, "in": first_in.timestamp.time() if first_in else None,
                        "out": last_out.timestamp.time() if last_out else None,
                        "hours": hours})

    return render(request, 'core/daily_performance.html', {
        'form': form,
        'results': results,
    })

@login_required
@staff_required
def manager_requests(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    pending_edits = EditRequest.objects.filter(status='pending')
    pending_leaves = LeaveRequest.objects.filter(status='pending')
    return render(request, 'core/manager_requests.html', {
        'pending_edits': pending_edits,
        'pending_leaves': pending_leaves,
    })

@login_required
@staff_required
def periodic_performance(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    form = UserLogsRangeForm(request.GET or None)
    results = []
    if form.is_valid():
        sd = form.cleaned_data.get('start_g')
        ed = form.cleaned_data.get('end_g')
        if sd and ed:
            for u in User.objects.all():
                logs = AttendanceLog.objects.filter(user=u, timestamp__date__gte=sd, timestamp__date__lte=ed).order_by('timestamp')
                total = 0
                start = None
                for log in logs:
                    if log.log_type == 'in':
                        start = log.timestamp
                    elif log.log_type == 'out' and start:
                        total += (log.timestamp - start).total_seconds()
                        start = None
                hours = round(total/3600, 2)
                results.append({'user': u, 'hours': hours})
    return render(request, 'core/periodic_performance.html', {
        'form': form,
        'results': results,
    })

@login_required
@staff_required
def device_settings(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    devices = AttendanceDevice.objects.all()
    return render(request, 'core/device_list.html', {
        'devices': devices,
    })

@login_required
@staff_required
def device_add(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == 'POST':
        form = AttendanceDeviceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'دستگاه ذخیره شد.')
            return redirect('device_settings')
    else:
        form = AttendanceDeviceForm()
    return render(request, 'core/device_form.html', {
        'form': form,
        'title': 'افزودن دستگاه',
    })

@login_required
@staff_required
def device_edit(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    device = get_object_or_404(AttendanceDevice, pk=pk)
    if request.method == 'POST':
        form = AttendanceDeviceForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            messages.success(request, 'دستگاه ویرایش شد.')
            return redirect('device_settings')
    else:
        form = AttendanceDeviceForm(instance=device)
    return render(request, 'core/device_form.html', {
        'form': form,
        'title': 'ویرایش دستگاه',
    })

@login_required
@staff_required
def device_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    device = get_object_or_404(AttendanceDevice, pk=pk)
    if request.method == 'POST':
        device.delete()
        messages.success(request, 'حذف شد.')
        return redirect('device_settings')
    return render(request, 'core/confirm_delete.html', {
        'title': 'حذف دستگاه',
        'object': device.name,
        'cancel_url': reverse('device_settings'),
    })

@login_required
@staff_required
def shifts(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    shifts = WorkShift.objects.all()
    return render(request, 'core/shift_list.html', {'shifts': shifts})

@login_required
@staff_required
def shift_add(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == 'POST':
        form = WorkShiftForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'شیفت ذخیره شد.')
            return redirect('shifts')
    else:
        form = WorkShiftForm()
    return render(request, 'core/shift_form.html', {'form': form, 'title': 'افزودن شیفت'})

@login_required
@staff_required
def shift_edit(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(WorkShift, pk=pk)
    if request.method == 'POST':
        form = WorkShiftForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'ذخیره شد.')
            return redirect('shifts')
    else:
        form = WorkShiftForm(instance=obj)
    return render(request, 'core/shift_form.html', {'form': form, 'title': 'ویرایش شیفت'})

@login_required
@staff_required
def shift_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(WorkShift, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'حذف شد.')
        return redirect('shifts')
    return render(request, 'core/confirm_delete.html', {
        'title': 'حذف شیفت',
        'object': obj.name,
        'cancel_url': reverse('shifts'),
    })

@login_required
@staff_required
def policies(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    policies = CompanyPolicy.objects.all()
    return render(request, 'core/policy_list.html', {'policies': policies})

@login_required
@staff_required
def policy_add(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == 'POST':
        form = CompanyPolicyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'سیاست ذخیره شد.')
            return redirect('policies')
    else:
        form = CompanyPolicyForm()
    return render(request, 'core/policy_form.html', {'form': form, 'title': 'افزودن سیاست'})

@login_required
@staff_required
def policy_edit(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(CompanyPolicy, pk=pk)
    if request.method == 'POST':
        form = CompanyPolicyForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'ذخیره شد.')
            return redirect('policies')
    else:
        form = CompanyPolicyForm(instance=obj)
    return render(request, 'core/policy_form.html', {'form': form, 'title': 'ویرایش سیاست'})

@login_required
@staff_required
def policy_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(CompanyPolicy, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'حذف شد.')
        return redirect('policies')
    return render(request, 'core/confirm_delete.html', {
        'title': 'حذف سیاست',
        'object': obj.title,
        'cancel_url': reverse('policies'),
    })

@login_required
@staff_required
def work_groups(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    groups = WorkGroup.objects.all()
    return render(request, 'core/workgroup_list.html', {'groups': groups})

@login_required
@staff_required
def workgroup_add(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == 'POST':
        form = WorkGroupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'گروه ذخیره شد.')
            return redirect('work_groups')
    else:
        form = WorkGroupForm()
    return render(request, 'core/workgroup_form.html', {'form': form, 'title': 'افزودن گروه'})

@login_required
@staff_required
def workgroup_edit(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(WorkGroup, pk=pk)
    if request.method == 'POST':
        form = WorkGroupForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'ذخیره شد.')
            return redirect('work_groups')
    else:
        form = WorkGroupForm(instance=obj)
    return render(request, 'core/workgroup_form.html', {'form': form, 'title': 'ویرایش گروه'})

@login_required
@staff_required
def workgroup_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(WorkGroup, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'حذف شد.')
        return redirect('work_groups')
    return render(request, 'core/confirm_delete.html', {
        'title': 'حذف گروه',
        'object': obj.name,
        'cancel_url': reverse('work_groups'),
    })

@login_required
@staff_required
def units(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    units = WorkUnit.objects.all()
    return render(request, 'core/unit_list.html', {'units': units})

@login_required
@staff_required
def unit_add(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == 'POST':
        form = WorkUnitForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'واحد ذخیره شد.')
            return redirect('units')
    else:
        form = WorkUnitForm()
    return render(request, 'core/unit_form.html', {'form': form, 'title': 'افزودن واحد'})

@login_required
@staff_required
def unit_edit(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(WorkUnit, pk=pk)
    if request.method == 'POST':
        form = WorkUnitForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'ذخیره شد.')
            return redirect('units')
    else:
        form = WorkUnitForm(instance=obj)
    return render(request, 'core/unit_form.html', {'form': form, 'title': 'ویرایش واحد'})

@login_required
@staff_required
def unit_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(WorkUnit, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'حذف شد.')
        return redirect('units')
    return render(request, 'core/confirm_delete.html', {
        'title': 'حذف واحد',
        'object': obj.name,
        'cancel_url': reverse('units'),
    })

@login_required
@staff_required
def request_types(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    types = RequestType.objects.all()
    return render(request, 'core/requesttype_list.html', {'types': types})

@login_required
@staff_required
def requesttype_add(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == 'POST':
        form = RequestTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'نوع درخواست ذخیره شد.')
            return redirect('request_types')
    else:
        form = RequestTypeForm()
    return render(request, 'core/requesttype_form.html', {'form': form, 'title': 'افزودن نوع درخواست'})

@login_required
@staff_required
def requesttype_edit(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(RequestType, pk=pk)
    if request.method == 'POST':
        form = RequestTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'ذخیره شد.')
            return redirect('request_types')
    else:
        form = RequestTypeForm(instance=obj)
    return render(request, 'core/requesttype_form.html', {'form': form, 'title': 'ویرایش نوع درخواست'})

@login_required
@staff_required
def requesttype_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(RequestType, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'حذف شد.')
        return redirect('request_types')
    return render(request, 'core/confirm_delete.html', {
        'title': 'حذف نوع درخواست',
        'object': obj.name,
        'cancel_url': reverse('request_types'),
    })

@login_required
@staff_required
def general_settings(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    return render(request, 'core/weekly_holidays.html', {'form': WeeklyHolidayForm(), 'active_tab': 'general_settings'})

@login_required
@staff_required
def my_account(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == 'POST':
        form = CustomUserSimpleForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'حساب شما به‌روزرسانی شد.')
            return redirect('my_account')
    else:
        form = CustomUserSimpleForm(instance=request.user)
    return render(request, 'core/user_form.html', {'form': form, 'title': 'حساب من'})

@login_required
@staff_required
def report_attendances(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    form = UserLogsRangeForm(request.GET or None)
    logs = []
    if form.is_valid():
        sd = form.cleaned_data.get('start_g')
        ed = form.cleaned_data.get('end_g')
        if sd and ed:
            logs = AttendanceLog.objects.select_related('user').filter(
                timestamp__date__gte=sd, timestamp__date__lte=ed
            ).order_by('-timestamp')
    return render(request, 'core/report_attendances.html', {
        'form': form,
        'logs': logs,
    })

@login_required
@staff_required
def report_requests(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    edit_qs = EditRequest.objects.select_related('user').order_by('-created_at')
    leave_qs = LeaveRequest.objects.select_related('user').order_by('-created_at')
    return render(request, 'core/report_requests.html', {
        'edits': edit_qs,
        'leaves': leave_qs,
    })

@login_required
@staff_required
def report_daily_performance(request):
    """نمایش کارکرد پرسنل در بازه دلخواه"""
    if not request.session.get("face_verified"):
        return redirect("management_face_check")

    form = UserRangeForm(request.GET or None)
    rows = []
    total_seconds = 0
    if form.is_valid():
        user = form.cleaned_data["user"]
        start = form.cleaned_data.get("start_g")
        end = form.cleaned_data.get("end_g")
        if start and end:
            day = start
            while day <= end:
                logs = AttendanceLog.objects.filter(
                    user=user, timestamp__date=day
                ).order_by("timestamp")
                first_in = logs.filter(log_type="in").first()
                last_out = logs.filter(log_type="out").last()
                daily = 0
                if first_in and last_out:
                    daily = (last_out.timestamp - first_in.timestamp).total_seconds()
                rows.append({
                    "date": day,
                    "in": first_in.timestamp.time() if first_in else None,
                    "out": last_out.timestamp.time() if last_out else None,
                    "hours": round(daily / 3600, 2),
                })
                total_seconds += daily
                day += timedelta(days=1)

    return render(request, "core/report_daily_performance.html", {
        "form": form,
        "rows": rows,
        "total_hours": round(total_seconds / 3600, 2),
    })

@login_required
@staff_required
def report_performance_calculation(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    return periodic_performance(request)


@login_required
@staff_required
def report_annual_requests(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    year = timezone.now().year
    stats = []
    for m in range(1,13):
        start = datetime(year, m, 1).date()
        if m == 12:
            end = datetime(year+1, 1, 1).date() - timedelta(days=1)
        else:
            end = datetime(year, m+1, 1).date() - timedelta(days=1)
        edits = EditRequest.objects.filter(created_at__date__range=(start, end)).count()
        leaves = LeaveRequest.objects.filter(created_at__date__range=(start, end)).count()
        stats.append({'month': m, 'edits': edits, 'leaves': leaves})
    return render(request, 'core/report_annual_requests.html', {'stats': stats})
