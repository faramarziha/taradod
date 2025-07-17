from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    personnel_code = models.CharField("کد پرسنلی", max_length=20, unique=True)
    national_id    = models.CharField("کد ملی", max_length=10, unique=True)
    face_encoding  = models.BinaryField(null=True, blank=True)
    face_image = models.ImageField("تصویر چهره", upload_to="faces/", null=True, blank=True)
    # اگر قبلاً فیلد face_image هم اضافه کرده‌اید، بگذارید

    def __str__(self):
        return f"{self.personnel_code} – {self.get_full_name()}"
