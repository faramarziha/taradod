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
    path('management/cartable/', views.management_cartable, name='management_cartable'),
    path('management/reports/', views.user_reports, name='management_reports'),
    path('management/suspicions/', views.suspicious_logs, name='suspicious_logs'),
    path('management/edit-requests/', views.edit_requests, name='edit_requests'),
    path('management/leave-requests/', views.leave_requests, name='leave_requests'),
    path('management/leave-requests/add/', views.add_leave, name='add_leave'),
    path('management/logs/export/', views.export_logs_csv, name='export_logs_csv'),
    path('management/attendance-status/', views.attendance_status, name='attendance_status'),
    path('management/attendance-status/api/', views.api_attendance_status, name='api_attendance_status'),
    path('management/mizkar/attendance/', views.attendance_status, name='mizkar_attendance'),
    path('management/mizkar/daily/', views.daily_performance, name='daily_performance'),
    path('management/mizkar/requests/', views.management_requests, name='management_requests'),
    path('management/mizkar/periodic/', views.periodic_performance, name='periodic_performance'),
    path('management/settings/devices/', views.device_settings, name='device_settings'),
    path('management/settings/shifts/', views.shift_settings, name='shift_settings'),
    path('management/settings/policies/', views.policy_settings, name='policy_settings'),
    path('management/settings/groups/', views.group_settings, name='group_settings'),
    path('management/settings/units/', views.unit_settings, name='unit_settings'),
    path('management/settings/request-types/', views.request_type_settings, name='request_type_settings'),
    path('management/settings/general/', views.general_settings, name='general_settings'),
    path('management/reports/requests/', views.report_requests, name='report_requests'),
    path('management/reports/daily/', views.report_daily, name='report_daily'),
    path('management/reports/calculation/', views.report_calculation, name='report_calculation'),
    path('management/reports/periodic/', views.report_periodic, name='report_periodic'),
    path('management/reports/annual-requests/', views.report_annual_requests, name='report_annual_requests'),
    path('management/account/', views.management_account, name='management_account'),

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
