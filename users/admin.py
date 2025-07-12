# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    # فیلدهای اضافی مربوط به تشخیص چهره را به بخش‌های نمایش اضافه می‌کنیم
    fieldsets = UserAdmin.fieldsets + (
        ("تشخیص چهره", {
            "fields": ("face_encoding", "face_image"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("face_encoding",)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("تشخیص چهره", {
            "fields": ("face_image",),
            "classes": ("wide",),
        }),
    )

    # ستون‌های لیست کاربران در صفحه ادمین
    list_display = (
        "personnel_code",
        "first_name",
        "last_name",
        "username",
        "national_id",
        "is_staff",
    )
    search_fields = (
        "personnel_code",
        "first_name",
        "last_name",
        "national_id",
    )
    list_filter = ("is_staff", "is_active")
