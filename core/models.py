from django.db import models

class AttendanceDevice(models.Model):
    name = models.CharField("نام دستگاه", max_length=50)
    location = models.CharField("مکان", max_length=100, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    last_seen = models.DateTimeField("آخرین اتصال", null=True, blank=True)

    def __str__(self):
        return self.name

class WorkShift(models.Model):
    name = models.CharField("نام شیفت", max_length=50)
    start_time = models.TimeField("شروع")
    end_time = models.TimeField("پایان")

    def __str__(self):
        return self.name

class CompanyPolicy(models.Model):
    title = models.CharField("عنوان", max_length=100)
    content = models.TextField("متن", blank=True)

    def __str__(self):
        return self.title

class WorkGroup(models.Model):
    name = models.CharField("نام گروه", max_length=50)
    description = models.TextField("توضیح", blank=True)

    def __str__(self):
        return self.name

class WorkUnit(models.Model):
    name = models.CharField("نام واحد", max_length=50)
    description = models.TextField("توضیح", blank=True)

    def __str__(self):
        return self.name

class RequestType(models.Model):
    name = models.CharField("نام درخواست", max_length=50)
    description = models.TextField("توضیح", blank=True)

    def __str__(self):
        return self.name
