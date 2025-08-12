import base64
import io
import json
import secrets
import os
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

from django.db.models import Count, Q

from attendance.models import (
    AttendanceLog,
    SuspiciousLog,
    EditRequest,
    LeaveRequest,
    WeeklyHoliday,
    Shift,
    Group,
    LeaveType,
)
from core.forms import (
    CustomUserSimpleForm,
    InquiryForm,
    EditRequestForm,
    LeaveRequestForm,
    ManualLogForm,
    ManualLeaveForm,
    AttendanceStatusForm,
    UserLogsRangeForm,
    WeeklyHolidayForm,
    ShiftForm,
    GroupForm,
    LeaveTypeForm,
    ReportFilterForm,
    MonthlyPerformanceForm,
)
from .models import Device

from users.models import CustomUser


User = get_user_model()


def _get_user_shift(user):
    """Return the effective shift for a user."""
    if getattr(user, "shift", None):
        return user.shift
    if getattr(user, "group", None) and user.group and user.group.shift:
        return user.group.shift
    return None


def _shift_bounds(date, shift):
    """Return start and end datetimes for the given date and shift."""
    start_dt = datetime.combine(date, shift.start_time)
    end_dt = datetime.combine(date, shift.end_time)
    if shift.end_time <= shift.start_time:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def _weekday_index(date):
    """Convert Python weekday (Mon=0) to app convention (Sat=0)."""
    return (date.weekday() + 2) % 7


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
    device, _ = Device.objects.get_or_create(id=1, defaults={"name": "Main device"})
    device.last_seen = timezone.now()
    device.save(update_fields=["last_seen"])
    if not device.is_active:
        return JsonResponse({"ok": False, "msg": "دستگاه غیرفعال است."})
    try:
        data = json.loads(request.body)
        img1 = data.get("image1")
        img2 = data.get("image2")
        if img1 and img2:
            enc1 = _get_face_encoding_from_base64(img1)
            enc2 = _get_face_encoding_from_base64(img2)
            if enc1 is None or enc2 is None:
                return JsonResponse({"ok": False, "msg": "چهره به‌وضوح دیده نشد. لطفاً روبه‌رو و در نور کافی قرار بگیرید."})
            movement = np.linalg.norm(enc1 - enc2)
            if movement < 0.08:
                return JsonResponse({"ok": False, "msg": "حرکت تشخیص داده نشد. لطفاً دستور روی صفحه را اجرا کنید."})
            enc = (enc1 + enc2) / 2
        else:
            enc = _get_face_encoding_from_base64(data.get("image", ""))
            if enc is None:
                return JsonResponse({"ok": False, "msg": "چهره به‌وضوح دیده نشد. لطفاً روبه‌رو و در نور کافی قرار بگیرید."})
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
                    if end_of_day.tzinfo is not None:
                        end_of_day = end_of_day.replace(tzinfo=None)
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
                raw_img = img1 or data.get("image", "")
                header, b64data = raw_img.split(",", 1)
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

        return JsonResponse({"ok": False, "msg": "چهره شما در سیستم ثبت نشده است."})
    except Exception:
        return JsonResponse({"ok": False, "msg": "خطا در پردازش تصویر. لطفاً دوباره تلاش کنید."})

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
    today = timezone.now().date()

    # Determine today's status for the user
    status = "holiday"
    first_in = None
    if not WeeklyHoliday.objects.filter(weekday=_weekday_index(today)).exists():
        logs = AttendanceLog.objects.filter(user=u, timestamp__date=today).order_by("timestamp")
        if logs.exists():
            status = "present"
            first_in = logs.first().timestamp.time()
        elif LeaveRequest.objects.filter(
            user=u,
            status="approved",
            start_date__lte=today,
            end_date__gte=today,
        ).exists():
            status = "leave"
        else:
            status = "absent"
    today_status = {"status": status, "first_in": first_in}

    # Gather recent notifications from leave and edit requests
    events = []
    leave_events = LeaveRequest.objects.filter(user=u).order_by("-created_at")[:4]
    for r in leave_events:
        msg = f"درخواست مرخصی شما برای تاریخ {r.start_date} تا {r.end_date} {r.get_status_display()}."
        events.append({"created_at": r.created_at, "message": msg})
    edit_events = EditRequest.objects.filter(user=u).order_by("-created_at")[:4]
    for r in edit_events:
        time_str = r.timestamp.strftime("%Y-%m-%d %H:%M")
        msg = f"درخواست ویرایش تردد شما برای {time_str} {r.get_status_display()}."
        events.append({"created_at": r.created_at, "message": msg})
    events = sorted(events, key=lambda x: x["created_at"], reverse=True)[:4]

    # Monthly performance statistics
    today_j = jdatetime.date.today()
    jy, jm = today_j.year, today_j.month
    days_in_month = jdatetime.j_days_in_month[jm - 1]
    total_work_seconds = 0
    total_delay_seconds = 0
    absent_days = 0
    shift = _get_user_shift(u)
    default_start = time(9, 0)
    default_end = time(17, 0)
    for d in range(1, days_in_month + 1):
        date_j = jdatetime.date(jy, jm, d)
        date_g = date_j.togregorian()
        if date_g > today:
            break
        if WeeklyHoliday.objects.filter(weekday=_weekday_index(date_g)).exists():
            continue
        if LeaveRequest.objects.filter(
            user=u,
            status="approved",
            start_date__lte=date_g,
            end_date__gte=date_g,
        ).exists():
            continue
        logs = AttendanceLog.objects.filter(user=u, timestamp__date=date_g).order_by("timestamp")
        if logs.exists():
            first_log = logs.first().timestamp
            last_log = logs.last().timestamp
            shift_start = shift.start_time if shift else default_start
            shift_end = shift.end_time if shift else default_end
            start_dt = datetime.combine(date_g, shift_start)
            end_dt = datetime.combine(date_g, shift_end)
            if shift_end <= shift_start:
                end_dt += timedelta(days=1)
            if first_log.tzinfo is not None:
                first_log = first_log.replace(tzinfo=None)
            if last_log.tzinfo is not None:
                last_log = last_log.replace(tzinfo=None)
            work_start = max(first_log, start_dt)
            work_end = min(last_log, end_dt)
            if work_end > work_start:
                total_work_seconds += (work_end - work_start).total_seconds()
            if first_log > start_dt:
                total_delay_seconds += (first_log - start_dt).total_seconds()
        else:
            absent_days += 1
    monthly_stats = {
        "total_hours": round(total_work_seconds / 3600, 2),
        "total_delay": int(total_delay_seconds / 60),
        "absent_days": absent_days,
    }

    # Attendance logs for selected month
    month_param = request.GET.get("month")
    if month_param:
        ly, lm = [int(x) for x in month_param.split("-")]
    else:
        t = jdatetime.date.today()
        ly, lm = t.year, t.month
    days = jdatetime.j_days_in_month[lm - 1]
    start_g = jdatetime.date(ly, lm, 1).togregorian()
    end_g = jdatetime.date(ly, lm, days).togregorian()
    qs = AttendanceLog.objects.filter(user=u, timestamp__date__range=(start_g, end_g)).order_by("timestamp")
    daily_logs = {d: {"in": None, "out": None} for d in range(1, days + 1)}
    for log in qs:
        jd = jdatetime.date.fromgregorian(date=log.timestamp.date())
        info = daily_logs.get(jd.day)
        if log.log_type == "in" and info["in"] is None:
            info["in"] = log.timestamp.time()
        if log.log_type == "out":
            info["out"] = log.timestamp.time()
    prev_m = (jdatetime.date(ly, lm, 1) - jdatetime.timedelta(days=1))
    next_m = (jdatetime.date(ly, lm, days) + jdatetime.timedelta(days=1))

    edit_requests = EditRequest.objects.filter(user=u).order_by("-created_at")
    leave_requests = LeaveRequest.objects.select_related("leave_type").filter(user=u).order_by("-created_at")

    return render(
        request,
        "core/user_profile.html",
        {
            "user": u,
            "today_status": today_status,
            "recent_events": events,
            "monthly_stats": monthly_stats,
            "daily_logs": daily_logs,
            "log_jyear": ly,
            "log_jmonth": lm,
            "prev_month": f"{prev_m.year}-{prev_m.month:02d}",
            "next_month": f"{next_m.year}-{next_m.month:02d}",
            "edit_requests": edit_requests,
            "leave_requests": leave_requests,
        },
    )



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
            if obj.timestamp.tzinfo is not None:
                obj.timestamp = obj.timestamp.replace(tzinfo=None)
            obj.save()
            messages.success(request, "درخواست شما ثبت شد و در انتظار تأیید است.")
            return redirect(reverse("user_profile") + "#edit-requests")
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
                return redirect(reverse("user_profile") + "#leave-requests")
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
    return redirect(reverse("user_profile") + "#edit-requests")


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
    return redirect(reverse("user_profile") + "#leave-requests")


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
    """Advanced user management center with filtering and bulk actions."""
    if not request.session.get("face_verified"):
        return redirect("management_face_check")

    # ---------- Bulk actions ----------
    if request.method == "POST":
        action = request.POST.get("bulk_action")
        selected_ids = request.POST.getlist("selected_users")
        if action and selected_ids:
            qs = User.objects.filter(id__in=selected_ids)
            if action == "deactivate":
                qs.update(is_active=False)
                messages.success(request, "کاربران انتخاب‌شده غیرفعال شدند.")
            elif action == "assign_group":
                group_id = request.POST.get("group")
                if group_id:
                    qs.update(group_id=group_id)
                    messages.success(request, "گروه کاربران به‌روزرسانی شد.")
            elif action == "assign_shift":
                shift_id = request.POST.get("shift")
                if shift_id:
                    qs.update(shift_id=shift_id)
                    messages.success(request, "شیفت کاربران به‌روزرسانی شد.")
            elif action == "delete":
                qs.delete()
                messages.success(request, "کاربران انتخاب‌شده حذف شدند.")
        return redirect("management_users")

    users = User.objects.all().select_related("group", "shift")

    # ---------- Filtering ----------
    q = request.GET.get("q")
    status = request.GET.get("status")
    group = request.GET.get("group")
    shift = request.GET.get("shift")
    face = request.GET.get("face")

    if q:
        users = users.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(personnel_code__icontains=q)
        )
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)
    if group:
        users = users.filter(group_id=group)
    if shift:
        users = users.filter(shift_id=shift)
    if face == "with":
        users = users.filter(face_encoding__isnull=False)
    elif face == "without":
        users = users.filter(face_encoding__isnull=True)

    ctx = {
        "users": users,
        "groups": Group.objects.all(),
        "shifts": Shift.objects.all(),
    }
    return render(request, "core/management_users.html", ctx)


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
@require_POST
def user_delete(request, pk):
    obj = get_object_or_404(User, pk=pk)
    if obj == request.user:
        messages.error(request, "نمی‌توانید خودتان را حذف کنید.")
    else:
        obj.delete()
        messages.success(request, "حذف موفق.")
    return redirect("management_users")


@login_required
@staff_required
def admin_user_profile(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")

    user_obj = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = CustomUserSimpleForm(request.POST, request.FILES, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات کاربر به‌روز شد.")
            return redirect("admin_user_profile", pk=pk)
    else:
        form = CustomUserSimpleForm(instance=user_obj)

    requests_form = UserLogsRangeForm(request.GET or None, prefix="req")
    edit_requests = EditRequest.objects.filter(user=user_obj).order_by("-created_at")
    leave_requests = LeaveRequest.objects.filter(user=user_obj).order_by("-created_at")
    if requests_form.is_valid():
        sd = requests_form.cleaned_data.get("start_g")
        ed = requests_form.cleaned_data.get("end_g")
        if sd and ed:
            edit_requests = edit_requests.filter(
                created_at__date__gte=sd, created_at__date__lte=ed
            )
            leave_requests = leave_requests.filter(
                created_at__date__gte=sd, created_at__date__lte=ed
            )

    return render(
        request,
        "core/admin_user_profile.html",
        {
            "user_obj": user_obj,
            "form": form,
            "requests_form": requests_form,
            "edit_requests": edit_requests,
            "leave_requests": leave_requests,
        },
    )


@require_POST
@login_required
@staff_required
def user_face_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    user_obj.face_encoding = None
    if user_obj.face_image:
        user_obj.face_image.delete(save=False)
    user_obj.face_image = None
    user_obj.save()
    messages.success(request, "چهره کاربر حذف شد.")
    return redirect("admin_user_profile", pk=pk)

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

    today = timezone.now().date()
    is_holiday = WeeklyHoliday.objects.filter(weekday=_weekday_index(today)).exists()

    group_id = request.GET.get("group")
    shift_id = request.GET.get("shift")

    users_qs = User.objects.all()
    if group_id:
        users_qs = users_qs.filter(group_id=group_id)
    if shift_id:
        users_qs = users_qs.filter(shift_id=shift_id)

    today_in_logs = AttendanceLog.objects.filter(
        user__in=users_qs, timestamp__date=today, log_type="in"
    ).count()
    today_out_logs = AttendanceLog.objects.filter(
        user__in=users_qs, timestamp__date=today, log_type="out"
    ).count()

    # لیست کارکنان حاضر، غایب و مرخصی
    if is_holiday:
        present_users = leave_users = absent_users = users_qs.none()
        present_ids = []
    else:
        present_ids = (
            AttendanceLog.objects.filter(user__in=users_qs, timestamp__date=today)
            .values_list("user_id", flat=True)
            .distinct()
        )
        leave_ids = (
            LeaveRequest.objects.filter(
                user__in=users_qs,
                start_date__lte=today,
                end_date__gte=today,
            )
            .values_list("user_id", flat=True)
            .distinct()
        )
        present_users = users_qs.filter(id__in=present_ids)
        leave_users = users_qs.filter(id__in=leave_ids)
        absent_users = users_qs.exclude(id__in=present_ids).exclude(id__in=leave_ids)

    tardy_users = User.objects.none()
    if not is_holiday:
        tardy_ids = []
        present_users_details = users_qs.filter(id__in=present_ids).select_related("shift", "group__shift")
        for user in present_users_details:
            shift = _get_user_shift(user)
            shift_start = time(9, 0)
            if shift:
                shift_start = shift.start_time
            first_log = AttendanceLog.objects.filter(user=user, timestamp__date=today).order_by("timestamp").first()
            if first_log:
                start_dt = datetime.combine(today, shift_start)
                first_dt = first_log.timestamp
                if first_dt.tzinfo is not None:
                    first_dt = first_dt.replace(tzinfo=None)
                if first_dt > start_dt:
                    tardy_ids.append(user.id)
        tardy_users = users_qs.filter(id__in=tardy_ids)

    # هشدارها
    pending_edit_objs = EditRequest.objects.select_related("user").filter(user__in=users_qs, status="pending")
    pending_leave_objs = LeaveRequest.objects.select_related("user").filter(user__in=users_qs, status="pending")
    pending_edits = pending_edit_objs.count()
    pending_leaves = pending_leave_objs.count()
    suspicious_today = SuspiciousLog.objects.filter(matched_user__in=users_qs, timestamp__date=today).count()

    # مرکز اقدامات فوری: ترکیب درخواست‌های مرخصی و ویرایش
    pending_actions = []
    for req in pending_edit_objs[:5]:
        pending_actions.append({
            "id": req.id,
            "user": req.user,
            "date": jdatetime.date.fromgregorian(date=req.timestamp.date()).strftime("%Y/%m/%d"),
            "type": "edit",
            "type_label": "ویرایش تردد",
            "action_url": reverse("edit_requests"),
        })
    for req in pending_leave_objs[:5]:
        pending_actions.append({
            "id": req.id,
            "user": req.user,
            "date": jdatetime.date.fromgregorian(date=req.start_date).strftime("%Y/%m/%d"),
            "type": "leave",
            "type_label": "مرخصی",
            "action_url": reverse("leave_requests"),
        })

    # خوب‌ها و بدها: آمار عملکرد یک ماه اخیر
    month_start = today - timedelta(days=30)
    tardy_stats = []
    streak_stats = []
    for u in users_qs:
        shift = _get_user_shift(u)
        shift_start = shift.start_time if shift else time(9, 0)
        tardies = 0
        for i in range(31):
            day = month_start + timedelta(days=i)
            first_log = (
                AttendanceLog.objects.filter(user=u, timestamp__date=day)
                .order_by("timestamp")
                .first()
            )
            if first_log:
                log_time = first_log.timestamp
                if log_time.tzinfo is not None:
                    log_time = log_time.replace(tzinfo=None)
                if log_time.time() > shift_start:
                    tardies += 1
        streak = 0
        for i in range(30):
            day = today - timedelta(days=i)
            first_log = (
                AttendanceLog.objects.filter(user=u, timestamp__date=day)
                .order_by("timestamp")
                .first()
            )
            if not first_log:
                break
            log_time = first_log.timestamp
            if log_time.tzinfo is not None:
                log_time = log_time.replace(tzinfo=None)
            if log_time.time() > shift_start:
                break
            streak += 1
        tardy_stats.append((u, tardies))
        streak_stats.append((u, streak))
    worst_performers = sorted(tardy_stats, key=lambda x: x[1], reverse=True)[:5]
    best_performers = sorted(streak_stats, key=lambda x: x[1], reverse=True)[:5]

    device = Device.objects.first()
    device_online = device.online if device else False

    context = {
        'active_tab': 'dashboard',
        'today_in_logs': today_in_logs,
        'today_out_logs': today_out_logs,
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
        'pending_actions': pending_actions,
        'worst_performers': worst_performers,
        'best_performers': best_performers,
        'device_online': device_online,
        'is_holiday': is_holiday,
        'groups': Group.objects.all(),
        'shifts': Shift.objects.all(),
        'selected_group': group_id,
        'selected_shift': shift_id,
    }
    return render(request, 'core/management_dashboard.html', context)


# ======= گزارش‌گیری کاربران =======
@login_required
@staff_required
def user_reports(request):
    # محاسبات آماری
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    no_face_users = User.objects.filter(face_encoding__isnull=True).count()

    form = ReportFilterForm(request.GET or None)
    logs_qs = AttendanceLog.objects.select_related('user').order_by('-timestamp')
    if form.is_valid():
        cd = form.cleaned_data
        if cd['start_date']:
            logs_qs = logs_qs.filter(timestamp__date__gte=cd['start_date'].togregorian())
        if cd['end_date']:
            logs_qs = logs_qs.filter(timestamp__date__lte=cd['end_date'].togregorian())
        if cd['groups']:
            logs_qs = logs_qs.filter(user__group__in=cd['groups'])
        if cd['shifts']:
            logs_qs = logs_qs.filter(user__shift__in=cd['shifts'])
        if cd['users']:
            logs_qs = logs_qs.filter(user__in=cd['users'])
        logs = list(logs_qs[:100])
    else:
        logs = list(logs_qs[:10])

    context = {
        'active_tab': 'reports',
        'active_users': active_users,
        'inactive_users': inactive_users,
        'no_face_users': no_face_users,
        'logs': logs,
        'form': form,
    }
    return render(request, 'core/user_reports.html', context)


@login_required
@staff_required
def monthly_profile(request):
    form = MonthlyPerformanceForm(request.GET or None)
    report = None
    logs = []
    leaves = []
    selected_user = None
    if form.is_valid():
        selected_user = form.cleaned_data['user']
        year = form.cleaned_data['year']
        month = int(form.cleaned_data['month'])
        start_j = jdatetime.date(year, month, 1)
        if month == 12:
            next_month = jdatetime.date(year + 1, 1, 1)
        else:
            next_month = jdatetime.date(year, month + 1, 1)
        end_j = next_month - jdatetime.timedelta(days=1)
        start_g = start_j.togregorian()
        end_g = end_j.togregorian()
        logs_qs = AttendanceLog.objects.filter(
            user=selected_user,
            timestamp__date__range=(start_g, end_g)
        ).order_by('timestamp')
        logs = list(logs_qs)
        logs_by_day = {}
        for log in logs:
            logs_by_day.setdefault(log.timestamp.date(), []).append(log)

        # prepare leave days
        leaves = LeaveRequest.objects.filter(
            user=selected_user,
            start_date__lte=end_g,
            end_date__gte=start_g,
            status='approved'
        )
        leave_days = set()
        for leave in leaves:
            cur = max(leave.start_date, start_g)
            while cur <= min(leave.end_date, end_g):
                leave_days.add(cur)
                cur += timedelta(days=1)

        shift = _get_user_shift(selected_user)
        shift_start = time(9, 0)
        shift_end = time(17, 0)
        if shift:
            shift_start = shift.start_time
            shift_end = shift.end_time
        # shift duration
        if shift_end <= shift_start:
            shift_minutes = (
                datetime.combine(start_g, shift_end) + timedelta(days=1) - datetime.combine(start_g, shift_start)
            ).seconds // 60
        else:
            shift_minutes = (
                datetime.combine(start_g, shift_end) - datetime.combine(start_g, shift_start)
            ).seconds // 60

        weekly_holidays = set(WeeklyHoliday.objects.values_list('weekday', flat=True))

        day = start_g
        total_minutes = 0
        mandatory_minutes = 0
        tardy_minutes = 0
        absence_days = 0
        while day <= end_g:
            if _weekday_index(day) in weekly_holidays or day in leave_days:
                day += timedelta(days=1)
                continue
            mandatory_minutes += shift_minutes
            day_logs = logs_by_day.get(day, [])
            if day_logs:
                current_in = None
                for log in day_logs:
                    if log.log_type == 'in':
                        current_in = log.timestamp
                    elif log.log_type == 'out' and current_in:
                        total_minutes += int((log.timestamp - current_in).total_seconds() // 60)
                        current_in = None
                first_log = day_logs[0]
                shift_start_dt = datetime.combine(day, shift_start)
                fl_ts = first_log.timestamp
                if fl_ts.tzinfo is not None:
                    fl_ts = fl_ts.replace(tzinfo=None)
                if fl_ts > shift_start_dt:
                    tardy_minutes += int((fl_ts - shift_start_dt).total_seconds() // 60)
            else:
                absence_days += 1
            day += timedelta(days=1)

        overtime_minutes = total_minutes - mandatory_minutes
        report = {
            'required_hours': round(mandatory_minutes / 60, 2),
            'present_hours': round(total_minutes / 60, 2),
            'overtime_minutes': overtime_minutes,
            'absence_days': absence_days,
            'tardy_minutes': tardy_minutes,
        }
    context = {
        'active_tab': 'reports',
        'form': form,
        'report': report,
        'logs': logs,
        'leaves': leaves,
        'selected_user': selected_user,
    }
    return render(request, 'core/monthly_profile.html', context)


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

    holiday = WeeklyHoliday.objects.filter(weekday=_weekday_index(target_date)).exists()
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

    holiday = WeeklyHoliday.objects.filter(weekday=_weekday_index(target_date)).exists()
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
    logs = (
        SuspiciousLog.objects.select_related('matched_user')
        .filter(status="pending")
        .order_by('-timestamp')[:50]
    )
    return render(request, 'core/suspicious_logs.html', {
        'active_tab': 'suspicions',
        'logs': logs,
    })


@login_required
@staff_required
@require_POST
def suspicious_log_action(request, pk):
    """Process manager action on a suspicious log."""
    log = get_object_or_404(SuspiciousLog, id=pk, status="pending")
    action = request.POST.get("action")
    if action == "confirm":
        if log.matched_user:
            u = log.matched_user
            last_log = AttendanceLog.objects.filter(user=u).order_by('-timestamp').first()
            today = timezone.now().date()
            if last_log and last_log.log_type == 'in' and last_log.timestamp.date() < today:
                end_of_day = datetime.combine(last_log.timestamp.date(), time(23, 59))
                if end_of_day.tzinfo is not None:
                    end_of_day = end_of_day.replace(tzinfo=None)
                AttendanceLog.objects.create(user=u, timestamp=end_of_day, log_type='out', source='auto')
            log_type = 'out' if last_log and last_log.log_type == 'in' else 'in'
            AttendanceLog.objects.create(user=u, timestamp=timezone.now(), log_type=log_type, source='manager')
            if request.POST.get('train') and log.image:
                try:
                    img = face_recognition.load_image_file(log.image.path)
                    encs = face_recognition.face_encodings(img)
                    if encs:
                        new_enc = encs[0]
                        if u.face_encoding:
                            old = np.frombuffer(u.face_encoding, dtype=np.float64)
                            new_enc = (old + new_enc) / 2
                        u.face_encoding = new_enc.tobytes()
                        if not u.face_image:
                            with log.image.open('rb') as f:
                                u.face_image.save(os.path.basename(log.image.name), ContentFile(f.read()), save=False)
                        u.save()
                except Exception:
                    pass
        log.status = 'confirmed'
        log.save(update_fields=['status'])
        messages.success(request, "تردد ثبت شد.")
    elif action == 'ignore':
        log.status = 'ignored'
        log.save(update_fields=['status'])
        messages.info(request, 'مورد حذف شد.')
    elif action == 'fraud':
        log.status = 'fraud'
        log.save(update_fields=['status'])
        messages.warning(request, 'به عنوان تقلب ثبت شد.')
    return redirect('suspicious_logs')


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
        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("edit_requests")
    group_id = request.GET.get("group")
    shift_id = request.GET.get("shift")

    requests = EditRequest.objects.select_related("user").filter(cancelled_by_user=False).order_by("-created_at")
    if group_id:
        requests = requests.filter(user__group_id=group_id)
    if shift_id:
        requests = requests.filter(user__shift_id=shift_id)
    return render(
        request,
        "core/edit_requests.html",
        {
            "active_tab": "edit_requests",
            "requests": requests,
            "groups": Group.objects.all(),
            "shifts": Shift.objects.all(),
            "selected_group": group_id,
            "selected_shift": shift_id,
        },
    )


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
        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("leave_requests")
    group_id = request.GET.get("group")
    shift_id = request.GET.get("shift")

    requests = (
        LeaveRequest.objects.select_related("user", "leave_type")
        .filter(cancelled_by_user=False)
        .order_by("-created_at")
    )
    if group_id:
        requests = requests.filter(user__group_id=group_id)
    if shift_id:
        requests = requests.filter(user__shift_id=shift_id)

    return render(
        request,
        "core/leave_requests.html",
        {
            "active_tab": "leave_requests",
            "requests": requests,
            "today": timezone.now().date(),
            "groups": Group.objects.all(),
            "shifts": Shift.objects.all(),
            "selected_group": group_id,
            "selected_shift": shift_id,
        },
    )


@login_required
@staff_required
def add_log(request):
    """Allow admin to manually register an attendance log for a user."""
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    if request.method == "POST":
        form = ManualLogForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "تردد ثبت شد.")
            return redirect("edit_requests")
    else:
        form = ManualLogForm()
    return render(request, "core/manual_log_form.html", {
        "active_tab": "edit_requests",
        "form": form,
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
def device_settings(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    device, _ = Device.objects.get_or_create(id=1, defaults={"name": "Main device"})
    if request.method == "POST" and device.online:
        action = request.POST.get('action')
        device.is_active = action != 'deactivate'
        device.save(update_fields=['is_active'])
        return redirect('device_settings')
    return render(request, 'core/device_settings.html', {'device': device, 'active_tab': 'settings'})

@login_required
@staff_required
def shift_list(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    shifts = Shift.objects.annotate(
        user_count=Count("customuser", distinct=True)
        + Count("groups__customuser", distinct=True)
    )
    return render(
        request,
        "core/shift_list.html",
        {"shifts": shifts, "active_tab": "settings"},
    )


@login_required
@staff_required
def shift_edit(request, pk=None):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    instance = Shift.objects.filter(pk=pk).first()
    if request.method == "POST":
        form = ShiftForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "شیفت ذخیره شد.")
            return redirect("shift_list")
    else:
        form = ShiftForm(instance=instance)
    return render(request, "core/shift_form.html", {"form": form, "active_tab": "settings"})


@require_POST
@login_required
@staff_required
def shift_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    shift = get_object_or_404(Shift, pk=pk)
    shift.delete()
    messages.success(request, "حذف شد.")
    return redirect("shift_list")


@login_required
@staff_required
def group_list(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    groups = (
        Group.objects.select_related("shift")
        .annotate(user_count=Count("customuser"))
        .all()
    )
    return render(
        request,
        "core/group_list.html",
        {"groups": groups, "active_tab": "settings"},
    )


@login_required
@staff_required
def group_edit(request, pk=None):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    instance = Group.objects.filter(pk=pk).first()
    if request.method == "POST":
        form = GroupForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "گروه ذخیره شد.")
            return redirect("group_list")
    else:
        form = GroupForm(instance=instance)
    return render(request, "core/group_form.html", {"form": form, "active_tab": "settings"})


@require_POST
@login_required
@staff_required
def group_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    grp = get_object_or_404(Group, pk=pk)
    grp.delete()
    messages.success(request, "حذف شد.")
    return redirect("group_list")


@login_required
@staff_required
def leave_type_list(request):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    types = LeaveType.objects.all()
    return render(request, "core/leave_type_list.html", {"types": types, "active_tab": "settings"})


@login_required
@staff_required
def leave_type_edit(request, pk=None):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    instance = LeaveType.objects.filter(pk=pk).first()
    if request.method == "POST":
        form = LeaveTypeForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "نوع مرخصی ذخیره شد.")
            return redirect("leave_type_list")
    else:
        form = LeaveTypeForm(instance=instance)
    return render(request, "core/leave_type_form.html", {"form": form, "active_tab": "settings"})


@require_POST
@login_required
@staff_required
def leave_type_delete(request, pk):
    if not request.session.get("face_verified"):
        return redirect("management_face_check")
    obj = get_object_or_404(LeaveType, pk=pk)
    obj.delete()
    messages.success(request, "حذف شد.")
    return redirect("leave_type_list")
