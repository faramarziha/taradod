import asyncio
from django.contrib.auth import get_user_model
from django.utils import timezone
from attendance.models import AttendanceLog

async def generate_attendance_report(start_date, end_date, user=None, group=None):
    """Collect attendance statistics asynchronously."""
    await asyncio.sleep(0)  # allow context switch
    qs = AttendanceLog.objects.filter(
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date,
    )
    if user is not None:
        qs = qs.filter(user=user)
    if group is not None:
        qs = qs.filter(user__group=group)
    data = []
    for log in qs.select_related('user'):
        data.append({
            'user': log.user.get_full_name(),
            'time': log.timestamp,
            'type': log.log_type,
        })
    return data
