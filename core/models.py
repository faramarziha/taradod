from datetime import timedelta

from django.db import models
from django.utils import timezone


class Device(models.Model):
    """Attendance kiosk device state."""

    name = models.CharField(max_length=100, unique=True, default="main")
    last_seen = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def is_online(self):
        if self.last_seen:
            return timezone.now() - self.last_seen < timedelta(seconds=20)
        return False

    def __str__(self):
        return self.name
