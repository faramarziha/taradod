from datetime import datetime, timedelta, date, time
import random

from django.core.management.base import BaseCommand
from faker import Faker

from attendance.models import (
    AttendanceLog,
    EditRequest,
    Group,
    LeaveRequest,
    LeaveType,
    Shift,
    WeeklyHoliday,
)
from users.models import CustomUser


class Command(BaseCommand):
    help = "Seed database with fake data for testing"

    def handle(self, *args, **options):
        fake = Faker("fa_IR")
        self.create_weekly_holidays()
        shifts = self.create_shifts()
        groups = self.create_groups(shifts)
        leave_types = self.create_leave_types()
        users = self.create_users(fake, groups)
        self.create_attendance_and_requests(users, leave_types)
        self.stdout.write(self.style.SUCCESS("Fake data generated."))

    def create_weekly_holidays(self):
        WeeklyHoliday.objects.get_or_create(weekday=5)
        WeeklyHoliday.objects.get_or_create(weekday=6)

    def create_shifts(self):
        data = [
            ("شیفت اول", time(8, 0), time(16, 0)),
            ("شیفت دوم", time(9, 0), time(17, 0)),
            ("شیفت سوم", time(10, 0), time(18, 0)),
        ]
        shifts = []
        for name, start, end in data:
            shift, created = Shift.objects.get_or_create(
                name=name, defaults={"start_time": start, "end_time": end}
            )
            if not created and (
                shift.start_time != start or shift.end_time != end
            ):
                shift.start_time = start
                shift.end_time = end
                shift.save()
            shifts.append(shift)
        return shifts

    def create_groups(self, shifts):
        names = ["گروه الف", "گروه ب", "گروه پ", "گروه ت", "گروه ث"]
        groups = []
        for name in names:
            shift = random.choice(shifts)
            group, created = Group.objects.get_or_create(
                name=name, defaults={"shift": shift}
            )
            if not group.shift:
                group.shift = shift
                group.save()
            groups.append(group)
        return groups

    def create_leave_types(self):
        names = ["استحقاقی", "استعلاجی", "بدون حقوق"]
        leave_types = []
        for name in names:
            lt, _ = LeaveType.objects.get_or_create(name=name)
            leave_types.append(lt)
        return leave_types

    def create_users(self, fake, groups):
        users = []
        for i in range(30):
            first = fake.first_name()
            last = fake.last_name()
            username = f"user{i+1}"
            personnel_code = f"{i+1:03d}"
            national_id = f"{i+1:05d}"
            group = random.choice(groups)
            user, created = CustomUser.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "personnel_code": personnel_code,
                    "national_id": national_id,
                    "group": group,
                    "shift": group.shift,
                },
            )
            if created:
                user.set_password("password")
                user.save()
            users.append(user)
        return users

    def create_attendance_and_requests(self, users, leave_types):
        today = date.today()
        start_3m = today - timedelta(days=90)
        start_2m = today - timedelta(days=60)

        group1 = users[:18]
        group2 = users[18:24]
        group3 = users[24:]

        # group1: perfect attendance, some with approved leaves
        leave_users = random.sample(group1, 7)
        for user in group1:
            leave_days = set()
            if user in leave_users:
                # two approved leaves in past three months
                possible_days = self.working_days(start_3m, today)
                leave_days = set(random.sample(possible_days, 2))
                for day in leave_days:
                    LeaveRequest.objects.get_or_create(
                        user=user,
                        start_date=day,
                        end_date=day,
                        status="approved",
                        leave_type=random.choice(leave_types),
                    )
            self.generate_logs(user, start_3m, today, leave_days)

        # group2: last two months with one incomplete log and one absence
        for user in group2:
            working_days = self.working_days(start_2m, today)
            incomplete_day = random.choice(working_days)
            remaining_days = [d for d in working_days if d != incomplete_day]
            absence_day = random.choice(remaining_days)

            for day in working_days:
                if day == incomplete_day:
                    self.generate_logs(user, day, day, incomplete=True)
                    # request for missing log
                    shift = user.shift
                    missing_time = datetime.combine(day, shift.end_time)
                    EditRequest.objects.get_or_create(
                        user=user,
                        timestamp=missing_time,
                        log_type="out",
                        status="pending",
                    )
                elif day == absence_day:
                    continue
                else:
                    self.generate_logs(user, day, day)

            # record absence? no logs already indicates absence

        # group3: perfect attendance + one future leave
        next_month_start = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        next_month_days = self.working_days(
            next_month_start, next_month_start + timedelta(days=30)
        )
        for user in group3:
            self.generate_logs(user, start_3m, today)
            leave_day = random.choice(next_month_days)
            LeaveRequest.objects.get_or_create(
                user=user,
                start_date=leave_day,
                end_date=leave_day,
                status="approved",
                leave_type=random.choice(leave_types),
            )

    def working_days(self, start, end):
        days = []
        day = start
        while day <= end:
            if day.weekday() not in [3, 4]:
                days.append(day)
            day += timedelta(days=1)
        return days

    def generate_logs(self, user, start, end, leave_days=None, incomplete=False):
        if leave_days is None:
            leave_days = set()
        day = start
        shift = user.shift
        while day <= end:
            if day.weekday() in [3, 4] or day in leave_days:
                day += timedelta(days=1)
                continue
            in_time = datetime.combine(day, shift.start_time) + timedelta(
                minutes=random.randint(-10, 10)
            )
            AttendanceLog.objects.get_or_create(
                user=user, timestamp=in_time, log_type="in"
            )
            if not incomplete:
                out_time = datetime.combine(day, shift.end_time) + timedelta(
                    minutes=random.randint(-10, 10)
                )
                AttendanceLog.objects.get_or_create(
                    user=user, timestamp=out_time, log_type="out"
                )
            day += timedelta(days=1)
