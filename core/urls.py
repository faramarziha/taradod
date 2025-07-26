from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    # صفحهٔ اصلی
    path("", views.home, name="home"),

    # لاگین/لاگ‌اوت
    path("management/login/", views.ManagementLoginView.as_view(), name="management_login"),
    path("device/login/",     views.DeviceLoginView.as_view(),     name="device_login"),
    path("logout/",           LogoutView.as_view(next_page="home"), name="logout"),
    path('management/dashboard/', views.management_dashboard, name='management_dashboard'),
    path('management/reports/', views.user_reports, name='management_reports'),
    path('management/suspicions/', views.suspicious_logs, name='suspicious_logs'),
    path('management/edit-requests/', views.edit_requests, name='edit_requests'),
    path('management/leave-requests/', views.leave_requests, name='leave_requests'),
    path('management/requests/', views.unified_requests, name='unified_requests'),
    path('management/leave-requests/add/', views.add_leave, name='add_leave'),
    path('management/logs/export/', views.export_logs_csv, name='export_logs_csv'),
    path('management/advanced-report/', views.attendance_report, name='attendance_report'),
    path('management/attendance-status/', views.attendance_status, name='attendance_status'),
    path('management/attendance-status/api/', views.api_attendance_status, name='api_attendance_status'),

    # مرحلهٔ دوم: ثبت یا تأیید چهرهٔ مدیر برای فعال‌سازی کیوسک
    path("device/face-check/",      views.device_face_check,              name="device_face_check"),
    path("device/face-check/api/",  views.api_device_verify_face,         name="api_device_verify_face"),
    # پس از موفقیت، وارد صفحهٔ اصلی کیوسک می‌شود
    path("device/",                 views.device_page,                    name="device_page"),

    # API ثبت تردد عادی (کیوسک)
    path("api/verify-face/",        views.api_verify_face,                name="api_verify_face"),
    path("api/register-face/",      views.api_register_face,              name="api_register_face"),

    # —————— کاربر عادی ——————
    path("user/inquiry/",           views.user_inquiry,                   name="user_inquiry"),
    path("user/profile/",           views.user_profile,                  name="user_profile"),
    path("user/workspace/",        views.user_workspace,                name="user_workspace"),
    path("user/logs/",              views.my_logs,                        name="my_logs"),
    path("user/logs/export/",      views.export_my_logs_csv,             name="export_my_logs_csv"),
    path("user/edit-request/",     views.edit_request,                  name="edit_request"),
    path("user/leave-request/",    views.leave_request,                 name="leave_request"),
    path("user/edit-request/<int:pk>/cancel/",  views.cancel_edit_request,  name="cancel_edit_request"),
    path("user/leave-request/<int:pk>/cancel/", views.cancel_leave_request, name="cancel_leave_request"),
    path("user/edit-requests/",    views.user_edit_requests,            name="user_edit_requests"),
    path("user/leave-requests/",   views.user_leave_requests,           name="user_leave_requests"),

    # —————— پنل مدیریت ——————
    # تأیید چهرهٔ مدیر قبل از ورود به پنل
    path("management/face-check/",     views.management_face_check,     name="management_face_check"),
    path("management/face-check/api/", views.api_management_verify_face, name="api_management_verify_face"),

    # مدیریت CRUD کاربران
    path("management/users/",                views.management_users,               name="management_users"),
    path("management/users/add/",            views.user_add,                       name="user_add"),
    path("management/users/<int:pk>/edit/",  views.user_update,                    name="user_update"),
    path("management/users/<int:pk>/delete/",views.user_delete,                    name="user_delete"),
    path("management/users/<int:user_id>/register-face/",
         views.register_face_page_for_user, name="register_face_page_for_user"),
    path("management/users/<int:user_id>/register-face/api/",
         views.register_face_api,            name="register_face_api"),
    path("management/weekly-holidays/", views.weekly_holidays, name="weekly_holidays"),
    path("management/users/<int:user_id>/logs/", views.user_logs_admin, name="user_logs_admin"),

    # مدیریت ساختار سازمانی و شیفت‌ها
    path("management/work-groups/", views.work_groups, name="work_groups"),
    path("management/work-groups/add/", views.work_group_add, name="work_group_add"),
    path("management/work-groups/<int:pk>/edit/", views.work_group_edit, name="work_group_edit"),
    path("management/work-groups/<int:pk>/delete/", views.work_group_delete, name="work_group_delete"),

    path("management/work-units/", views.work_units, name="work_units"),
    path("management/work-units/add/", views.work_unit_add, name="work_unit_add"),
    path("management/work-units/<int:pk>/edit/", views.work_unit_edit, name="work_unit_edit"),
    path("management/work-units/<int:pk>/delete/", views.work_unit_delete, name="work_unit_delete"),

    path("management/shifts/", views.shifts, name="shifts"),
    path("management/shifts/add/", views.shift_add, name="shift_add"),
    path("management/shifts/<int:pk>/edit/", views.shift_edit, name="shift_edit"),
    path("management/shifts/<int:pk>/delete/", views.shift_delete, name="shift_delete"),

    path("management/policies/", views.policies, name="policies"),
    path("management/policies/add/", views.policy_add, name="policy_add"),
    path("management/policies/<int:pk>/edit/", views.policy_edit, name="policy_edit"),
    path("management/policies/<int:pk>/delete/", views.policy_delete, name="policy_delete"),

    path("management/calendars/", views.calendars, name="calendars"),
    path("management/calendars/add/", views.calendar_add, name="calendar_add"),
    path("management/calendars/<int:pk>/edit/", views.calendar_edit, name="calendar_edit"),
    path("management/calendars/<int:pk>/delete/", views.calendar_delete, name="calendar_delete"),

    path("management/settings/", views.general_settings, name="general_settings"),
]
