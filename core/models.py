from datetime import timedelta

from django.db import models
from django.utils import timezone


class Device(models.Model):
    """Attendance device registered in the system."""

    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    @property
    def online(self) -> bool:
        if not self.last_seen:
            return False
        return timezone.now() - self.last_seen < timedelta(minutes=1)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return self.name
