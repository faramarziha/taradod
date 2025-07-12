from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import AttendanceLog
import jdatetime


@login_required
def my_logs(request):
    uid = request.session.get("inquiry_user_id")
    if not uid:
        return redirect("user_inquiry")
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(id=uid)
    logs = AttendanceLog.objects.filter(user=user).order_by("-timestamp")
    for l in logs:
        jal = jdatetime.datetime.fromgregorian(datetime=l.timestamp)
        l.shamsi = jal.strftime("%Y/%m/%d %H:%M:%S")
    return render(request, "attendance/my_logs.html", {"logs": logs, "user": user})
