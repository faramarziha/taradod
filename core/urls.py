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
    path('management/cartable/', views.manager_cartable, name='manager_cartable'),
    path('management/daily-performance/', views.daily_performance, name='daily_performance'),
    path('management/requests/', views.manager_requests, name='manager_requests'),
    path('management/periodic-performance/', views.periodic_performance, name='periodic_performance'),
    path('management/device-settings/', views.device_settings, name='device_settings'),
    path('management/device-settings/add/', views.device_add, name='device_add'),
    path('management/device-settings/<int:pk>/edit/', views.device_edit, name='device_edit'),
    path('management/device-settings/<int:pk>/delete/', views.device_delete, name='device_delete'),
    path('management/shifts/', views.shifts, name='shifts'),
    path('management/shifts/add/', views.shift_add, name='shift_add'),
    path('management/shifts/<int:pk>/edit/', views.shift_edit, name='shift_edit'),
    path('management/shifts/<int:pk>/delete/', views.shift_delete, name='shift_delete'),
    path('management/policies/', views.policies, name='policies'),
    path('management/policies/add/', views.policy_add, name='policy_add'),
    path('management/policies/<int:pk>/edit/', views.policy_edit, name='policy_edit'),
    path('management/policies/<int:pk>/delete/', views.policy_delete, name='policy_delete'),
    path('management/work-groups/', views.work_groups, name='work_groups'),
    path('management/work-groups/add/', views.workgroup_add, name='workgroup_add'),
    path('management/work-groups/<int:pk>/edit/', views.workgroup_edit, name='workgroup_edit'),
    path('management/work-groups/<int:pk>/delete/', views.workgroup_delete, name='workgroup_delete'),
    path('management/units/', views.units, name='units'),
    path('management/units/add/', views.unit_add, name='unit_add'),
    path('management/units/<int:pk>/edit/', views.unit_edit, name='unit_edit'),
    path('management/units/<int:pk>/delete/', views.unit_delete, name='unit_delete'),
    path('management/request-types/', views.request_types, name='request_types'),
    path('management/request-types/add/', views.requesttype_add, name='requesttype_add'),
    path('management/request-types/<int:pk>/edit/', views.requesttype_edit, name='requesttype_edit'),
    path('management/request-types/<int:pk>/delete/', views.requesttype_delete, name='requesttype_delete'),
    path('management/general-settings/', views.general_settings, name='general_settings'),
    path('management/my-account/', views.my_account, name='my_account'),
    path('management/reports/attendances/', views.report_attendances, name='report_attendances'),
    path('management/reports/requests/', views.report_requests, name='report_requests'),
    path('management/reports/daily-performance/', views.report_daily_performance, name='report_daily_performance'),
    path('management/reports/performance-calculation/', views.report_performance_calculation, name='report_performance_calculation'),
    path('management/reports/annual-requests/', views.report_annual_requests, name='report_annual_requests'),
    path('management/reports/', views.user_reports, name='management_reports'),
    path('management/suspicions/', views.suspicious_logs, name='suspicious_logs'),
    path('management/edit-requests/', views.edit_requests, name='edit_requests'),
    path('management/leave-requests/', views.leave_requests, name='leave_requests'),
    path('management/leave-requests/add/', views.add_leave, name='add_leave'),
    path('management/logs/export/', views.export_logs_csv, name='export_logs_csv'),
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
    path("user/logs/",              views.my_logs,                        name="my_logs"),
    path("user/logs/export/",      views.export_my_logs_csv,             name="export_my_logs_csv"),
    path("user/edit-request/",     views.edit_request,                  name="edit_request"),
    path("user/leave-request/",    views.leave_request,                 name="leave_request"),
    path("user/edit-request/<int:pk>/cancel/",  views.cancel_edit_request,  name="cancel_edit_request"),
    path("user/leave-request/<int:pk>/cancel/", views.cancel_leave_request, name="cancel_leave_request"),
    path("user/edit-requests/",    views.user_edit_requests,            name="user_edit_requests"),
    path("user/leave-requests/",   views.user_leave_requests,           name="user_leave_requests"),
    path("user/performance/",      views.my_performance,                name="my_performance"),

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
]
