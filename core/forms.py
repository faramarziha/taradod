from django import forms
from django.contrib.auth import get_user_model
from django_jalali import forms as jforms
from django_jalali.admin.widgets import AdminjDateWidget
import jdatetime
from attendance.models import EditRequest, LeaveRequest, LOG_TYPE_CHOICES
from attendance.models import WeeklyHoliday

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


class EditRequestForm(forms.ModelForm):
    date = jforms.jDateField(label="تاریخ", widget=AdminjDateWidget())
    log_type = forms.ChoiceField(choices=LOG_TYPE_CHOICES, label="نوع تردد")
    time = forms.TimeField(
        label="ساعت",
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": 60}),
    )

    class Meta:
        model = EditRequest
        fields = ["date", "time", "log_type", "note"]
        labels = {
            "note": "توضیح",
        }
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.timestamp:
            jd = jdatetime.datetime.fromgregorian(datetime=self.instance.timestamp)
            self.initial.setdefault("date", jd.date())
            self.initial.setdefault(
                "time",
                jd.time().replace(second=0, microsecond=0),
            )
        if self.instance.pk and self.instance.log_type:
            self.initial.setdefault("log_type", self.instance.log_type)

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        time_val = cleaned_data.get("time")
        if date and time_val:
            jdt = jdatetime.datetime(
                date.year,
                date.month,
                date.day,
                time_val.hour,
                time_val.minute,
                time_val.second,
            )
            cleaned_data["timestamp"] = jdt.togregorian()
        user = self.user or cleaned_data.get("user")
        ts = cleaned_data.get("timestamp")
        if user and ts:
            if EditRequest.objects.filter(user=user, timestamp=ts).exists():
                raise forms.ValidationError("برای این زمان قبلاً درخواست ثبت شده است.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.timestamp = self.cleaned_data["timestamp"]
        instance.log_type = self.cleaned_data["log_type"]
        if self.user is not None:
            instance.user = self.user
        if commit:
            instance.save()
        return instance


class LeaveRequestForm(forms.ModelForm):
    start_date = jforms.jDateField(label="از تاریخ", widget=AdminjDateWidget())
    duration = forms.IntegerField(label="مدت (روز)", min_value=1)

    class Meta:
        model = LeaveRequest
        fields = ["start_date", "duration", "reason"]
        labels = {
            "reason": "توضیح",
        }
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        sd = cleaned_data.get("start_date")
        dur = cleaned_data.get("duration")
        if sd:
            cleaned_data["start_date"] = sd.togregorian()
        if sd and dur:
            end_j = sd + jdatetime.timedelta(days=dur - 1)
            cleaned_data["end_date"] = end_j.togregorian()
            cleaned_data["end_jalali"] = end_j
        user = self.user or cleaned_data.get("user")
        if user and sd and dur:
            if LeaveRequest.objects.filter(user=user, start_date=sd.togregorian(), end_date=end_j.togregorian()).exists():
                raise forms.ValidationError("برای این بازه قبلاً درخواستی ثبت شده است.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.start_date = self.cleaned_data["start_date"]
        instance.end_date = self.cleaned_data["end_date"]
        if self.user is not None:
            instance.user = self.user
        if commit:
            instance.save()
        return instance


class ManualLeaveForm(forms.ModelForm):
    """Form for admins to directly register a leave for a user."""

    user = forms.ModelChoiceField(queryset=User.objects.all(), label="کاربر")
    start_date = jforms.jDateField(label="از تاریخ", widget=AdminjDateWidget())
    end_date = jforms.jDateField(label="تا تاریخ", widget=AdminjDateWidget())

    class Meta:
        model = LeaveRequest
        fields = ["user", "start_date", "end_date", "reason"]
        labels = {"reason": "توضیح"}
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned_data = super().clean()
        sd = cleaned_data.get("start_date")
        ed = cleaned_data.get("end_date")
        if sd and ed and ed < sd:
            self.add_error("end_date", "بازه نامعتبر است")
        if sd:
            cleaned_data["start_date"] = sd.togregorian()
        if ed:
            cleaned_data["end_date"] = ed.togregorian()
        user = cleaned_data.get("user")
        if user and sd and ed:
            if LeaveRequest.objects.filter(user=user, start_date=sd.togregorian(), end_date=ed.togregorian()).exists():
                raise forms.ValidationError("برای این بازه قبلاً درخواستی ثبت شده است.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.cleaned_data["user"]
        instance.start_date = self.cleaned_data["start_date"]
        instance.end_date = self.cleaned_data["end_date"]
        if commit:
            instance.save()
        return instance


class AttendanceStatusForm(forms.Form):
    """Simple form to pick a Jalali date for attendance status."""
    date = jforms.jDateField(
        label="تاریخ",
        widget=AdminjDateWidget(),
        required=False,
    )


class UserLogsRangeForm(forms.Form):
    start = jforms.jDateField(label="از تاریخ", widget=AdminjDateWidget())
    end = jforms.jDateField(label="تا تاریخ", widget=AdminjDateWidget())

    def clean(self):
        cleaned = super().clean()
        sd = cleaned.get("start")
        ed = cleaned.get("end")
        if sd:
            cleaned["start_g"] = sd.togregorian()
        if ed:
            cleaned["end_g"] = ed.togregorian()
        if sd and ed and cleaned["end_g"] < cleaned["start_g"]:
            self.add_error("end", "بازه نامعتبر است")
        return cleaned


class WeeklyHolidayForm(forms.Form):
    days = forms.MultipleChoiceField(
        choices=[
            (0, "شنبه"),
            (1, "یکشنبه"),
            (2, "دوشنبه"),
            (3, "سه‌شنبه"),
            (4, "چهارشنبه"),
            (5, "پنجشنبه"),
            (6, "جمعه"),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="روزهای تعطیل",
    )

from .models import (
    AttendanceDevice, WorkShift, CompanyPolicy, WorkGroup, WorkUnit, RequestType
)

class AttendanceDeviceForm(forms.ModelForm):
    class Meta:
        model = AttendanceDevice
        fields = ["name", "location", "is_active"]

class WorkShiftForm(forms.ModelForm):
    class Meta:
        model = WorkShift
        fields = ["name", "start_time", "end_time"]
        widgets = {
            "start_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "end_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        }

class CompanyPolicyForm(forms.ModelForm):
    class Meta:
        model = CompanyPolicy
        fields = ["title", "content"]
        widgets = {"content": forms.Textarea(attrs={"rows":3})}

class WorkGroupForm(forms.ModelForm):
    class Meta:
        model = WorkGroup
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows":3})}

class WorkUnitForm(forms.ModelForm):
    class Meta:
        model = WorkUnit
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows":3})}

class RequestTypeForm(forms.ModelForm):
    class Meta:
        model = RequestType
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows":3})}

