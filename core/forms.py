from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class InquiryForm(forms.Form):
    personnel_code = forms.CharField(label="کد پرسنلی", max_length=20)
    national_id    = forms.CharField(label="کد ملی",     max_length=10)

class CustomUserSimpleForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "personnel_code",
            "national_id",
            "is_active",
            "is_staff",
        ]
