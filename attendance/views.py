from django.shortcuts import render, redirect

from .models import AttendanceLog
import jdatetime


def my_logs(request):
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(id=uid)
    month = request.GET.get("month")
    if month:
        jy, jm = [int(x) for x in month.split("-")]
    else:
        t = jdatetime.date.today()
        jy, jm = t.year, t.month
    days = jdatetime.j_days_in_month[jm - 1]
    start_g = jdatetime.date(jy, jm, 1).togregorian()
    end_g = jdatetime.date(jy, jm, days).togregorian()
    qs = AttendanceLog.objects.filter(
        user=user, timestamp__date__range=(start_g, end_g)
    ).order_by("timestamp")
    daily = {d: {"in": [], "out": []} for d in range(1, days + 1)}
    for log in qs:
        jd = jdatetime.date.fromgregorian(date=log.timestamp.date())
        if log.log_type == "in":
            daily[jd.day]["in"].append(log.timestamp.time())
        else:
            daily[jd.day]["out"].append(log.timestamp.time())
    prev_m = (jdatetime.date(jy, jm, 1) - jdatetime.timedelta(days=1))
    next_m = (jdatetime.date(jy, jm, days) + jdatetime.timedelta(days=1))
    context = {
        "user": user,
        "daily_logs": daily,
        "jyear": jy,
        "jmonth": jm,
        "prev_month": f"{prev_m.year}-{prev_m.month:02d}",
        "next_month": f"{next_m.year}-{next_m.month:02d}",
    }
    return render(request, "attendance/my_logs.html", context)
