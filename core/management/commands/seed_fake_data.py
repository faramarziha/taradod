from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import (
    AttendanceLog,
    SuspiciousLog,
    EditRequest,
    LeaveRequest,
    WeeklyHoliday,
    Shift,
    Group,
    LeaveType,
    SOURCE_CHOICES,
)
from core.models import Device
from users.models import CustomUser
from faker import Faker
import random
from datetime import timedelta, datetime, time


class Command(BaseCommand):
    help = "Populate the database with roughly three months of realistic fake data."

    def handle(self, *args, **options):
        fake = Faker("fa_IR")
        Faker.seed(0)
        random.seed(0)

        # Create shifts
        shift_defs = [
            ("Morning", time(8, 0), time(16, 0)),
            ("Evening", time(16, 0), time(0, 0)),
            ("Night", time(0, 0), time(8, 0)),
        ]
        shifts = []
        for name, start, end in shift_defs:
            shift, _ = Shift.objects.get_or_create(
                name=name, defaults={"start_time": start, "end_time": end}
            )
            shifts.append(shift)

        # Create groups
        groups = []
        for i in range(1, 6):
            group, _ = Group.objects.get_or_create(
                name=f"Group {i}",
                defaults={"shift": random.choice(shifts)},
            )
            groups.append(group)

        # Leave types
        leave_type_names = ["Vacation", "Sick", "Personal"]
        leave_types = []
        for lt in leave_type_names:
            obj, _ = LeaveType.objects.get_or_create(
                name=lt, defaults={"description": fake.sentence()}
            )
            leave_types.append(obj)

        # Weekly holidays (Thursday & Friday)
        for day in [5, 6]:
            WeeklyHoliday.objects.get_or_create(weekday=day)

        # Devices
        for i in range(2):
            Device.objects.get_or_create(
                name=f"Device {i+1}",
                defaults={"last_seen": timezone.now() - timedelta(minutes=random.randint(0, 1000))},
            )

        # Users
        users = []
        for i in range(25):
            username = f"user{i+1}"
            user, created = CustomUser.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "personnel_code": f"{1000 + i}",
                    "national_id": str(
                        fake.unique.random_number(digits=10, fix_len=True)
                    ),
                    "group": random.choice(groups),
                    "shift": random.choice(shifts),
                },
            )
            if created:
                user.set_password("password")
                user.save()
            users.append(user)

        # Leave requests
        for user in users:
            for _ in range(random.randint(0, 3)):
                start = fake.date_between(start_date="-3M", end_date="today")
                length = random.randint(1, 3)
                end = start + timedelta(days=length)
                LeaveRequest.objects.get_or_create(
                    user=user,
                    start_date=start,
                    end_date=end,
                    defaults={
                        "reason": fake.sentence(),
                        "leave_type": random.choice(leave_types),
                        "status": random.choice([c[0] for c in LeaveRequest.STATUS_CHOICES]),
                    },
                )

        start_date = timezone.now().date() - timedelta(days=90)
        # Attendance logs & edit requests
        for day_offset in range(90):
            current_date = start_date + timedelta(days=day_offset)
            for user in users:
                # Skip if user on leave
                if LeaveRequest.objects.filter(
                    user=user, start_date__lte=current_date, end_date__gte=current_date
                ).exists():
                    continue
                # 80% chance user attended
                if random.random() < 0.8:
                    shift = user.shift or random.choice(shifts)
                    in_dt = datetime.combine(
                        current_date, shift.start_time
                    ) + timedelta(minutes=random.randint(-15, 15))
                    out_dt = datetime.combine(
                        current_date, shift.end_time
                    ) + timedelta(minutes=random.randint(-15, 15))
                    AttendanceLog.objects.create(
                        user=user,
                        timestamp=in_dt,
                        log_type="in",
                        source=random.choice([c[0] for c in SOURCE_CHOICES]),
                    )
                    AttendanceLog.objects.create(
                        user=user,
                        timestamp=out_dt,
                        log_type="out",
                        source=random.choice([c[0] for c in SOURCE_CHOICES]),
                    )
                else:
                    # maybe user creates edit request for missing log
                    if random.random() < 0.3:
                        missing_time = datetime.combine(current_date, time(9, 0))
                        EditRequest.objects.get_or_create(
                            user=user,
                            timestamp=missing_time,
                            defaults={
                                "log_type": "in",
                                "note": fake.sentence(),
                                "status": random.choice(
                                    [c[0] for c in EditRequest.STATUS_CHOICES]
                                ),
                            },
                        )

        # Suspicious logs
        from django.db import connection

        with connection.cursor() as cursor:
            columns = [
                col.name
                for col in connection.introspection.get_table_description(
                    cursor, SuspiciousLog._meta.db_table
                )
            ]
        has_status = "status" in columns

        if has_status:
            for _ in range(50):
                SuspiciousLog.objects.create(
                    matched_user=random.choice(users),
                    similarity=random.uniform(0, 1),
                    timestamp=timezone.now()
                    - timedelta(days=random.randint(0, 90), minutes=random.randint(0, 1440)),
                    status=random.choice([c[0] for c in SuspiciousLog.STATUS_CHOICES]),
                )

        self.stdout.write(self.style.SUCCESS("Fake data generated."))
