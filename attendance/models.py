from django.db import models
from django.conf import settings
from django.utils import timezone

# نوع رویداد تردد
LOG_TYPE_CHOICES = [
    ("in", "ورود"),
    ("out", "خروج"),
]

# منبع ثبت تردد
SOURCE_CHOICES = [
    ("self", "کارمند"),
    ("manager", "مدیر"),
]

# ثبت هر ورود و خروج
class AttendanceLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    log_type = models.CharField(max_length=4, choices=LOG_TYPE_CHOICES, default="in")
    source = models.CharField(max_length=7, choices=SOURCE_CHOICES, default="self")

    def __str__(self):
        return f"{self.user.username} - {self.timestamp:%Y-%m-%d %H:%M:%S}"

# لاگ‌های مشکوک با تصویر
class SuspiciousLog(models.Model):

    STATUS_CHOICES = [
        ("pending", "در انتظار"),
        ("confirmed", "تأیید شده"),
        ("ignored", "نادیده گرفته شده"),
        ("fraud", "تقلب"),
    ]
    matched_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User with the closest match",
    )
    similarity = models.FloatField(help_text="Euclidean distance of embedding")
    image = models.ImageField(
        upload_to="suspects/",
        null=True,
        blank=True,
        help_text="Captured image triggering the log",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        user_part = self.matched_user.username if self.matched_user else "Unknown"
        return f"{user_part} ? {self.similarity:.3f} ({self.status})"

# درخواست اصلاح تردد
class EditRequest(models.Model):

    STATUS_CHOICES = [
        ("pending", "در انتظار"),
        ("approved", "تأیید شده"),
        ("rejected", "رد شده"),
        ("cancelled", "لغو شده"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(help_text="زمان مورد نظر")
    log_type = models.CharField(max_length=4, choices=LOG_TYPE_CHOICES, default="in")
    note = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    manager_note = models.TextField(blank=True)
    cancelled_by_user = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "timestamp"], name="unique_user_timestamp"
            )
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.timestamp:%Y-%m-%d %H:%M}"

# درخواست مرخصی
class LeaveRequest(models.Model):

    STATUS_CHOICES = [
        ("pending", "در انتظار"),
        ("approved", "تأیید شده"),
        ("rejected", "رد شده"),
        ("cancelled", "لغو شده"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    leave_type = models.ForeignKey(
        "attendance.LeaveType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="نوع مرخصی",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    decision_at = models.DateTimeField(null=True, blank=True)
    manager_note = models.TextField(blank=True)
    cancelled_by_user = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "start_date", "end_date"],
                name="unique_user_leave_range",
            )
        ]

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            from django.core.exceptions import ValidationError

            raise ValidationError({"end_date": "بازه نامعتبر است"})

    def __str__(self):
        return f"{self.user.username} {self.start_date} - {self.end_date}"

# روزهای تعطیل هفتگی
class WeeklyHoliday(models.Model):

    WEEKDAY_CHOICES = [
        (0, "شنبه"),
        (1, "یکشنبه"),
        (2, "دوشنبه"),
        (3, "سه‌شنبه"),
        (4, "چهارشنبه"),
        (5, "پنجشنبه"),
        (6, "جمعه"),
    ]

    weekday = models.PositiveSmallIntegerField(unique=True, choices=WEEKDAY_CHOICES)

    def __str__(self):
        return dict(self.WEEKDAY_CHOICES).get(self.weekday, str(self.weekday))

# شیفت کاری
class Shift(models.Model):

    name = models.CharField(max_length=50, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return self.name

# گروه کارکنان
class Group(models.Model):

    name = models.CharField(max_length=50, unique=True)
    shift = models.ForeignKey(
        Shift, null=True, blank=True, on_delete=models.SET_NULL, related_name="groups"
    )

    def __str__(self):
        return self.name

# نوع مرخصی
class LeaveType(models.Model):

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
