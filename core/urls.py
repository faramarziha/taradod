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
    path('management/edit-requests/add-log/', views.add_log, name='add_log'),
    path('management/leave-requests/', views.leave_requests, name='leave_requests'),
    path('management/leave-requests/add/', views.add_leave, name='add_leave'),
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
    path("management/users/<int:pk>/profile/", views.admin_user_profile, name="admin_user_profile"),
    path("management/users/<int:pk>/face-delete/", views.user_face_delete, name="user_face_delete"),
    path("management/users/<int:user_id>/register-face/",
         views.register_face_page_for_user, name="register_face_page_for_user"),
    path("management/users/<int:user_id>/register-face/api/",
         views.register_face_api,            name="register_face_api"),
    path("management/weekly-holidays/", views.weekly_holidays, name="weekly_holidays"),
    path("management/device/", views.device_settings, name="device_settings"),
    path("management/shifts/", views.shift_list, name="shift_list"),
    path("management/shifts/add/", views.shift_edit, name="shift_add"),
    path("management/shifts/<int:pk>/edit/", views.shift_edit, name="shift_edit"),
    path("management/shifts/<int:pk>/delete/", views.shift_delete, name="shift_delete"),
    path("management/groups/", views.group_list, name="group_list"),
    path("management/groups/add/", views.group_edit, name="group_add"),
    path("management/groups/<int:pk>/edit/", views.group_edit, name="group_edit"),
    path("management/groups/<int:pk>/delete/", views.group_delete, name="group_delete"),
    path("management/leave-types/", views.leave_type_list, name="leave_type_list"),
    path("management/leave-types/add/", views.leave_type_edit, name="leave_type_add"),
    path("management/leave-types/<int:pk>/edit/", views.leave_type_edit, name="leave_type_edit"),
    path("management/leave-types/<int:pk>/delete/", views.leave_type_delete, name="leave_type_delete"),
    path("management/users/<int:user_id>/logs/", views.user_logs_admin, name="user_logs_admin"),
]
