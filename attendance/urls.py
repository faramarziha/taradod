from django.urls import path
from .views import my_logs

urlpatterns = [
    path("my-logs/", my_logs, name="my_logs"),
]
