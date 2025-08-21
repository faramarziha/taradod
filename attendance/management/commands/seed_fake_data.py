from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
import random
from datetime import datetime, timedelta, time

from attendance.models import (
    WeeklyHoliday,
    Shift,
    Group,
    LeaveType,
    AttendanceLog,
    LeaveRequest,
    EditRequest,
)
from users.models import CustomUser


class Command(BaseCommand):
    help = "Populate the database with realistic fake data using Faker"

    def handle(self, *args, **options):
        fake = Faker("fa_IR")
        random.seed(0)

        # Define weekly holidays
        for weekday in [5, 6]:  # Thursday and Friday
            WeeklyHoliday.objects.get_or_create(weekday=weekday)

        # Create shifts
        shift_morning, _ = Shift.objects.get_or_create(
            name="شیفت صبح", defaults={"start_time": time(8, 0), "end_time": time(16, 0)}
        )
        shift_evening, _ = Shift.objects.get_or_create(
            name="شیفت عصر", defaults={"start_time": time(16, 0), "end_time": time(23, 59)}
        )
        shift_night, _ = Shift.objects.get_or_create(
            name="شیفت شب", defaults={"start_time": time(0, 0), "end_time": time(8, 0)}
        )
        shifts = [shift_morning, shift_evening, shift_night]

        # Create groups
        group_names = [
            "گروه اداری",
            "گروه فنی",
            "گروه مالی",
            "گروه فروش",
            "گروه پشتیبانی",
        ]
        groups = []
        for name in group_names:
            group, _ = Group.objects.get_or_create(
                name=name, defaults={"shift": random.choice(shifts)}
            )
            groups.append(group)

        # Create leave types
        leave_type_names = [
            "مرخصی استحقاقی",
            "مرخصی استعلاجی",
            "مرخصی بدون حقوق",
        ]
        leave_types = []
        for name in leave_type_names:
            lt, _ = LeaveType.objects.get_or_create(name=name)
            leave_types.append(lt)

        # Generate users
        users = []
        used_personnel = set()
        used_national = set()
        for _ in range(30):
            while True:
                personnel_code = f"{random.randint(0, 999):03d}"
                if personnel_code not in used_personnel:
                    used_personnel.add(personnel_code)
                    break
            while True:
                national_id = f"{random.randint(0, 99999):05d}"
                if national_id not in used_national:
                    used_national.add(national_id)
                    break
            first_name = fake.first_name()
            last_name = fake.last_name()
            group = random.choice(groups)
            user = CustomUser.objects.create_user(
                username=f"user{personnel_code}",
                first_name=first_name,
                last_name=last_name,
                personnel_code=personnel_code,
                national_id=national_id,
                group=group,
                shift=group.shift,
                password="password123",
            )
            users.append(user)

        today = timezone.now().date()
        three_months_ago = today - timedelta(days=90)
        two_months_ago = today - timedelta(days=60)

        def daterange(start, end):
            for n in range((end - start).days + 1):
                yield start + timedelta(n)

        # Helper to create logs
        def create_logs(user, start_date):
            for day in daterange(start_date, today - timedelta(days=1)):
                if day.weekday() in (3, 4):  # Skip Thursday & Friday
                    continue
                if day in user_leave_days.get(user, set()):
                    continue
                shift = user.shift
                in_time = datetime.combine(day, shift.start_time) + timedelta(
                    minutes=random.randint(0, 5)
                )
                out_time = datetime.combine(day, shift.end_time) + timedelta(
                    minutes=random.randint(0, 5)
                )
                AttendanceLog.objects.create(user=user, timestamp=in_time, log_type="in")
                AttendanceLog.objects.create(user=user, timestamp=out_time, log_type="out")

        # First 18 users with perfect logs
        first_18 = users[:18]
        user_leave_days = {u: set() for u in first_18}
        leave_users = random.sample(first_18, 7)
        for u in leave_users:
            for _ in range(2):
                while True:
                    leave_day = three_months_ago + timedelta(
                        days=random.randint(0, 89)
                    )
                    if leave_day.weekday() in (3, 4) or leave_day in user_leave_days[u]:
                        continue
                    user_leave_days[u].add(leave_day)
                    LeaveRequest.objects.create(
                        user=u,
                        start_date=leave_day,
                        end_date=leave_day,
                        leave_type=random.choice(leave_types),
                        status="approved",
                        decision_at=timezone.now(),
                    )
                    break
        for u in first_18:
            create_logs(u, three_months_ago)

        # Next 6 users with one incomplete log and one absence
        next_6 = users[18:24]
        for u in next_6:
            absence_day = None
            incomplete_day = None
            while True:
                d = two_months_ago + timedelta(days=random.randint(0, 59))
                if d.weekday() not in (3, 4):
                    absence_day = d
                    break
            while True:
                d = two_months_ago + timedelta(days=random.randint(0, 59))
                if d.weekday() in (3, 4) or d == absence_day:
                    continue
                incomplete_day = d
                break
            for day in daterange(two_months_ago, today - timedelta(days=1)):
                if day.weekday() in (3, 4) or day == absence_day:
                    continue
                shift = u.shift
                in_time = datetime.combine(day, shift.start_time)
                out_time = datetime.combine(day, shift.end_time)
                if day == incomplete_day:
                    # Only check-in log
                    AttendanceLog.objects.create(
                        user=u, timestamp=in_time, log_type="in"
                    )
                    EditRequest.objects.create(
                        user=u,
                        timestamp=out_time,
                        log_type="out",
                        status="pending",
                    )
                else:
                    AttendanceLog.objects.create(
                        user=u,
                        timestamp=in_time + timedelta(minutes=random.randint(0, 5)),
                        log_type="in",
                    )
                    AttendanceLog.objects.create(
                        user=u,
                        timestamp=out_time + timedelta(minutes=random.randint(0, 5)),
                        log_type="out",
                    )

        # Last 6 users with future leave
        last_6 = users[24:]
        next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        for u in last_6:
            create_logs(u, three_months_ago)
            leave_day = next_month + timedelta(days=random.randint(0, 20))
            LeaveRequest.objects.create(
                user=u,
                start_date=leave_day,
                end_date=leave_day,
                leave_type=random.choice(leave_types),
                status="pending",
            )

        self.stdout.write(self.style.SUCCESS("Fake data generated successfully."))
