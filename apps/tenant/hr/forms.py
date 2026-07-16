from django import forms

from apps.tenant.orgsettings.models import Campus
from apps.tenant.users.models import Role

from .models import Department, DepartmentHead, Position, StaffProfile


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["campus", "name", "code", "is_active"]

    def __init__(self, *args, **kwargs):
        campuses = kwargs.pop("campuses", None)
        super().__init__(*args, **kwargs)
        self.fields["campus"].queryset = campuses if campuses is not None else Campus.objects.all()


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["department", "title", "is_active"]

    def __init__(self, *args, **kwargs):
        departments = kwargs.pop("departments", None)
        super().__init__(*args, **kwargs)
        if departments is not None:
            self.fields["department"].queryset = departments


class StaffProfileForm(forms.ModelForm):
    create_user = forms.BooleanField(required=False)
    username = forms.CharField(required=False)
    role_code = forms.ChoiceField(required=False, choices=Role.CODE_CHOICES)

    class Meta:
        model = StaffProfile
        fields = [
            "campus",
            "staff_id",
            "first_name",
            "last_name",
            "phone",
            "email",
            "staff_category",
            "department",
            "position",
            "reports_to",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        campuses = kwargs.pop("campuses", None)
        departments = kwargs.pop("departments", None)
        staff_queryset = kwargs.pop("staff_queryset", None)
        super().__init__(*args, **kwargs)
        self.fields["campus"].queryset = campuses if campuses is not None else Campus.objects.all()
        if departments is not None:
            self.fields["department"].queryset = departments
        if departments is not None:
            self.fields["position"].queryset = self.fields["position"].queryset.filter(department__in=departments)
        if staff_queryset is not None:
            self.fields["reports_to"].queryset = staff_queryset


class DepartmentHeadForm(forms.ModelForm):
    class Meta:
        model = DepartmentHead
        fields = ["department", "staff", "start_date", "end_date", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        departments = kwargs.pop("departments", None)
        staff_queryset = kwargs.pop("staff_queryset", None)
        super().__init__(*args, **kwargs)
        if departments is not None:
            self.fields["department"].queryset = departments
        if staff_queryset is not None:
            self.fields["staff"].queryset = staff_queryset
