from django.contrib import admin
from .models import (
    AttendanceLog,
    SuspiciousLog,
    EditRequest,
    LeaveRequest,
    Policy,
    WorkGroup,
    WorkUnit,
    Shift,
    Calendar,
    GeneralSetting,
)

@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ("user", "timestamp", "log_type", "source")
    list_filter  = ("user", "log_type", "source")


@admin.register(SuspiciousLog)
class SuspiciousLogAdmin(admin.ModelAdmin):
    list_display = ("matched_user", "similarity", "timestamp")
    list_filter = ("matched_user",)


@admin.register(EditRequest)
class EditRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "timestamp", "log_type", "status", "created_at")
    list_filter = ("status", "user", "log_type")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "start_date", "end_date", "status", "created_at")
    list_filter = ("status", "user")

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "late_tolerance", "overtime_rate", "annual_leave_days")

@admin.register(WorkGroup)
class WorkGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "supervisor")
    list_filter = ("supervisor",)

@admin.register(WorkUnit)
class WorkUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "group")
    list_filter = ("group",)

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("name", "start_time", "end_time")

@admin.register(Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = ("date", "user", "work_unit", "shift")
    list_filter = ("shift", "work_unit")


@admin.register(GeneralSetting)
class GeneralSettingAdmin(admin.ModelAdmin):
    list_display = ("company_name", "timezone", "time_correction", "week_start")
