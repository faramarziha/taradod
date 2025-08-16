from django.contrib import admin
from .models import AttendanceLog, SuspiciousLog, EditRequest, LeaveRequest

@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ("user", "timestamp", "log_type", "source")
    list_filter  = ("user", "log_type", "source")

@admin.register(SuspiciousLog)
class SuspiciousLogAdmin(admin.ModelAdmin):
    list_display = ("matched_user", "similarity", "status", "timestamp")
    list_filter = ("matched_user", "status")

@admin.register(EditRequest)
class EditRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "timestamp", "log_type", "status", "created_at")
    list_filter = ("status", "user", "log_type")

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "start_date", "end_date", "status", "created_at")
    list_filter = ("status", "user")
