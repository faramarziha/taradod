from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from datetime import datetime, timedelta, time
import random

from users.models import CustomUser
from attendance.models import (
    AttendanceLog,
    EditRequest,
    LeaveRequest,
    LeaveType,
    Group,
    Shift,
    WeeklyHoliday,
)


class Command(BaseCommand):
    help = "Populate database with fake attendance data using Faker"

    def handle(self, *args, **options):
        faker = Faker("fa_IR")
        random.seed(0)

        # Weekly holidays: Thursday and Friday
        WeeklyHoliday.objects.get_or_create(weekday=5)
        WeeklyHoliday.objects.get_or_create(weekday=6)

        # Shifts
        shift_defs = [
            ("شیفت صبح", time(8, 0), time(16, 0)),
            ("شیفت عصر", time(14, 0), time(22, 0)),
            ("شیفت شب", time(0, 0), time(8, 0)),
        ]
        shifts = []
        for name, start, end in shift_defs:
            shift, _ = Shift.objects.get_or_create(
                name=name,
                defaults={"start_time": start, "end_time": end},
            )
            # ensure times are up to date
            shift.start_time = start
            shift.end_time = end
            shift.save()
            shifts.append(shift)

        # Groups
        group_names = ["توسعه", "فروش", "مالی", "اداری", "پشتیبانی"]
        groups = []
        for name in group_names:
            shift = random.choice(shifts)
            group, created = Group.objects.get_or_create(name=name)
            group.shift = shift
            group.save()
            groups.append(group)

        # Leave types
        leave_type_names = [
            "مرخصی استحقاقی",
            "مرخصی استعلاجی",
            "مرخصی بدون حقوق",
        ]
        leave_types = []
        for name in leave_type_names:
            lt, _ = LeaveType.objects.get_or_create(name=name)
            leave_types.append(lt)

        # Users
        users = []
        for i in range(1, 31):
            personnel_code = f"{i:03}"
            national_id = f"{10000 + i:05}"
            group = random.choice(groups)
            user = CustomUser.objects.create_user(
                username=personnel_code,
                first_name=faker.first_name(),
                last_name=faker.last_name(),
                password="password",
                personnel_code=personnel_code,
                national_id=national_id,
                group=group,
                shift=group.shift,
            )
            users.append(user)

        today = timezone.now().date()
        three_months_ago = today - timedelta(days=90)
        two_months_ago = today - timedelta(days=60)

        # Category 1: 18 users, full attendance for 3 months
        cat1 = users[:18]
        cat1_with_leave = random.sample(cat1, 7)
        leave_days = {}
        for u in cat1_with_leave:
            workdays = [
                three_months_ago + timedelta(days=d)
                for d in range((today - three_months_ago).days)
                if (three_months_ago + timedelta(days=d)).weekday() not in (3, 4)
            ]
            chosen = random.sample(workdays, 2)
            leave_days[u] = chosen
            for day in chosen:
                LeaveRequest.objects.create(
                    user=u,
                    start_date=day,
                    end_date=day,
                    leave_type=random.choice(leave_types),
                    status="approved",
                    decision_at=timezone.now(),
                )

        for u in cat1:
            shift = u.shift
            d = three_months_ago
            while d <= today:
                if d.weekday() not in (3, 4) and d not in leave_days.get(u, []):
                    start_dt = datetime.combine(d, shift.start_time) + timedelta(
                        minutes=random.randint(-10, 10)
                    )
                    end_dt = datetime.combine(d, shift.end_time) + timedelta(
                        minutes=random.randint(-10, 10)
                    )
                    AttendanceLog.objects.create(user=u, timestamp=start_dt, log_type="in")
                    AttendanceLog.objects.create(user=u, timestamp=end_dt, log_type="out")
                d += timedelta(days=1)

        # Category 2: 6 users, last two months, one incomplete and one absence
        cat2 = users[18:24]
        for u in cat2:
            shift = u.shift
            workdays = [
                two_months_ago + timedelta(days=d)
                for d in range((today - two_months_ago).days)
                if (two_months_ago + timedelta(days=d)).weekday() not in (3, 4)
            ]
            incomplete_day = random.choice(workdays)
            remaining = [d for d in workdays if d != incomplete_day]
            absence_day = random.choice(remaining)
            for day in workdays:
                if day == absence_day:
                    continue
                if day == incomplete_day:
                    start_dt = datetime.combine(day, shift.start_time) + timedelta(
                        minutes=random.randint(-10, 10)
                    )
                    AttendanceLog.objects.create(user=u, timestamp=start_dt, log_type="in")
                    missing_dt = datetime.combine(day, shift.end_time)
                    EditRequest.objects.create(
                        user=u,
                        timestamp=missing_dt,
                        log_type="out",
                        note="درخواست ثبت خروج",
                        status="pending",
                    )
                else:
                    start_dt = datetime.combine(day, shift.start_time) + timedelta(
                        minutes=random.randint(-10, 10)
                    )
                    end_dt = datetime.combine(day, shift.end_time) + timedelta(
                        minutes=random.randint(-10, 10)
                    )
                    AttendanceLog.objects.create(user=u, timestamp=start_dt, log_type="in")
                    AttendanceLog.objects.create(user=u, timestamp=end_dt, log_type="out")

        # Category 3: remaining 6 users, full attendance and future leave
        cat3 = users[24:]
        for u in cat3:
            shift = u.shift
            d = three_months_ago
            while d <= today:
                if d.weekday() not in (3, 4):
                    start_dt = datetime.combine(d, shift.start_time) + timedelta(
                        minutes=random.randint(-10, 10)
                    )
                    end_dt = datetime.combine(d, shift.end_time) + timedelta(
                        minutes=random.randint(-10, 10)
                    )
                    AttendanceLog.objects.create(user=u, timestamp=start_dt, log_type="in")
                    AttendanceLog.objects.create(user=u, timestamp=end_dt, log_type="out")
                d += timedelta(days=1)

            next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            future_days = [
                next_month + timedelta(days=i)
                for i in range(30)
                if (next_month + timedelta(days=i)).weekday() not in (3, 4)
            ]
            day = random.choice(future_days)
            LeaveRequest.objects.create(
                user=u,
                start_date=day,
                end_date=day,
                leave_type=random.choice(leave_types),
                status="pending",
            )

        self.stdout.write(self.style.SUCCESS("Fake data generated successfully."))
