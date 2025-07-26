from django.db import models
from django.conf import settings
from django.utils import timezone

LOG_TYPE_CHOICES = [
    ("in", "ورود"),
    ("out", "خروج"),
]

SOURCE_CHOICES = [
    ("self", "کاربر"),
    ("auto", "سیستم"),
    ("manager", "مدیر"),
]

class AttendanceLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    log_type = models.CharField(max_length=4, choices=LOG_TYPE_CHOICES, default="in")
    source = models.CharField(max_length=7, choices=SOURCE_CHOICES, default="self")

    def __str__(self):
        return f"{self.user.username} - {self.timestamp:%Y-%m-%d %H:%M:%S}"


class SuspiciousLog(models.Model):
    """Log for near matches that require admin review."""
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

    def __str__(self):
        if self.matched_user:
            return f"{self.matched_user.username} ? {self.similarity:.3f}"
        return f"Unknown ? {self.similarity:.3f}"


class EditRequest(models.Model):
    """Employee request for adding a missing attendance log."""

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


class LeaveRequest(models.Model):
    """Employee leave request for a specific date range."""

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


class WeeklyHoliday(models.Model):
    """Days of week that are considered holidays (0=Monday)."""

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


class Shift(models.Model):
    """Simple shift definition with start and end times."""

    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return self.name


class Group(models.Model):
    """Group of users optionally tied to a shift."""

    name = models.CharField(max_length=50)
    shift = models.ForeignKey(
        Shift, null=True, blank=True, on_delete=models.SET_NULL, related_name="groups"
    )

    def __str__(self):
        return self.name


class LeaveType(models.Model):
    """Types of leaves (e.g. vacation, sick)."""

    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

