from django import forms
from django.contrib.auth import get_user_model
from django_jalali import forms as jforms
import jdatetime
from attendance import models as attendance_models
from attendance.models import (
    AttendanceLog,
    EditRequest,
    LeaveRequest,
    LOG_TYPE_CHOICES,
    Group,
    Shift,
)

User = get_user_model()

# ورودی تاریخ شمسی
class JalaliDateInput(forms.TextInput):

    def __init__(self, attrs=None):
        base_attrs = {"data-jdp": "", "data-jdp-only-date": ""}
        if attrs:
            base_attrs.update(attrs)
        super().__init__(attrs=base_attrs)

# ورودی زمان شمسی
class JalaliTimeInput(forms.TextInput):

    def __init__(self, attrs=None):
        base_attrs = {"data-jdp": "", "data-jdp-only-time": ""}
        if attrs:
            base_attrs.update(attrs)
        super().__init__(attrs=base_attrs)

# فرم استعلام کاربر
class InquiryForm(forms.Form):
    personnel_code = forms.CharField(label="کد پرسنلی", max_length=20)
    national_id    = forms.CharField(label="کد ملی",     max_length=10)

# فرم ساده کاربر
class CustomUserSimpleForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "personnel_code",
            "national_id",
            "group",
            "shift",
            "is_active",
            "is_staff",
        ]

# فرم درخواست ویرایش تردد
class EditRequestForm(forms.ModelForm):
    date = jforms.jDateField(label="تاریخ", widget=JalaliDateInput())
    log_type = forms.ChoiceField(choices=LOG_TYPE_CHOICES, label="نوع تردد")
    time = forms.TimeField(label="ساعت", widget=JalaliTimeInput())

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
        self.fields["date"].widget.attrs["data-jdp-max-date"] = "today"
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

# فرم درخواست مرخصی
class LeaveRequestForm(forms.ModelForm):
    start_date = jforms.jDateField(label="از تاریخ", widget=JalaliDateInput())
    duration = forms.IntegerField(label="مدت (روز)", min_value=1)
    leave_type = forms.ModelChoiceField(
        queryset=attendance_models.LeaveType.objects.all(),
        label="نوع مرخصی",
        required=False,
    )

    class Meta:
        model = LeaveRequest
        fields = ["leave_type", "start_date", "duration", "reason"]
        labels = {
            "leave_type": "نوع مرخصی",
            "reason": "توضیح",
        }
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["start_date"].widget.attrs["data-jdp-min-date"] = "today"

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
        instance.leave_type = self.cleaned_data.get("leave_type")
        if commit:
            instance.save()
        return instance

# ثبت تردد دستی
class ManualLogForm(forms.Form):

    user = forms.ModelChoiceField(queryset=User.objects.all(), label="کارمند")
    date = jforms.jDateField(label="تاریخ", widget=JalaliDateInput())
    time = forms.TimeField(label="ساعت", widget=JalaliTimeInput())
    log_type = forms.ChoiceField(choices=LOG_TYPE_CHOICES, label="نوع تردد")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].widget.attrs["data-jdp-max-date"] = "today"

    def clean(self):
        cleaned = super().clean()
        date_val = cleaned.get("date")
        time_val = cleaned.get("time")
        if date_val and time_val:
            jdt = jdatetime.datetime(
                date_val.year,
                date_val.month,
                date_val.day,
                time_val.hour,
                time_val.minute,
            )
            cleaned["timestamp"] = jdt.togregorian()
        user = cleaned.get("user")
        ts = cleaned.get("timestamp")
        if user and ts:
            if AttendanceLog.objects.filter(user=user, timestamp=ts).exists():
                raise forms.ValidationError("برای این زمان قبلاً ترددی ثبت شده است.")
        return cleaned

    def save(self):
        return AttendanceLog.objects.create(
            user=self.cleaned_data["user"],
            timestamp=self.cleaned_data["timestamp"],
            log_type=self.cleaned_data["log_type"],
            source="manager",
        )

# ثبت مرخصی دستی
class ManualLeaveForm(forms.ModelForm):

    user = forms.ModelChoiceField(queryset=User.objects.all(), label="کارمند")
    start_date = jforms.jDateField(label="از تاریخ", widget=JalaliDateInput())
    end_date = jforms.jDateField(label="تا تاریخ", widget=JalaliDateInput())

    leave_type = forms.ModelChoiceField(
        queryset=attendance_models.LeaveType.objects.all(),
        label="نوع مرخصی",
        required=False,
    )

    class Meta:
        model = LeaveRequest
        fields = ["user", "leave_type", "start_date", "end_date", "reason"]
        labels = {"reason": "توضیح", "leave_type": "نوع مرخصی"}
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

# فرم وضعیت حضور
class AttendanceStatusForm(forms.Form):

    date = jforms.jDateField(
        label="تاریخ",
        widget=JalaliDateInput(),
        required=False,
    )

# فرم بازه گزارش تردد
class UserLogsRangeForm(forms.Form):
    start = jforms.jDateField(label="از تاریخ", widget=JalaliDateInput())
    end = jforms.jDateField(label="تا تاریخ", widget=JalaliDateInput())

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

# انتخاب روزهای تعطیل
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

# فرم شیفت کاری
class ShiftForm(forms.ModelForm):
    class Meta:
        model = attendance_models.Shift
        fields = ["name", "start_time", "end_time"]
        labels = {
            "name": "نام",
            "start_time": "شروع",
            "end_time": "پایان",
        }
        widgets = {
            "start_time": JalaliTimeInput(),
            "end_time": JalaliTimeInput(),
        }

# فرم گروه کارکنان
class GroupForm(forms.ModelForm):
    class Meta:
        model = attendance_models.Group
        fields = ["name", "shift"]
        labels = {
            "name": "نام",
            "shift": "شیفت",
        }

# فرم نوع مرخصی
class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = attendance_models.LeaveType
        fields = ["name", "description"]
        labels = {"name": "نام", "description": "توضیح"}

# فیلتر گزارش‌ها
class ReportFilterForm(forms.Form):
    start_date = jforms.jDateField(
        label="از تاریخ",
        widget=JalaliDateInput(
            attrs={
                "placeholder": "۱۴۰۳/۰۵/۱۰",
                "class": "date-input vjDateField",
            }
        ),
        required=False,
    )
    end_date = jforms.jDateField(
        label="تا تاریخ",
        widget=JalaliDateInput(
            attrs={
                "placeholder": "۱۴۰۳/۰۵/۱۰",
                "class": "date-input vjDateField",
            }
        ),
        required=False,
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        label="گروه‌ها",
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "multi-select"}),
    )
    shifts = forms.ModelMultipleChoiceField(
        queryset=Shift.objects.all(),
        label="شیفت‌ها",
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "multi-select"}),
    )
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        label="کارکنان",
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "multi-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["users"].label_from_instance = (
            lambda obj: f"{obj.personnel_code} – {obj.first_name} {obj.last_name}"
        )

# فرم عملکرد ماهانه
class MonthlyPerformanceForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all(), label="کارمند")
    year = forms.IntegerField(label="سال", initial=jdatetime.date.today().year)
    MONTH_CHOICES = [
        (1, "فروردین"),
        (2, "اردیبهشت"),
        (3, "خرداد"),
        (4, "تیر"),
        (5, "مرداد"),
        (6, "شهریور"),
        (7, "مهر"),
        (8, "آبان"),
        (9, "آذر"),
        (10, "دی"),
        (11, "بهمن"),
        (12, "اسفند"),
    ]
    month = forms.ChoiceField(label="ماه", choices=MONTH_CHOICES, initial=jdatetime.date.today().month)
