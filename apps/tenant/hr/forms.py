from django import forms

from apps.tenant.users.models import Role

from .models import Department, DepartmentHead, Position, StaffProfile


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["campus", "name", "code", "is_active"]


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["department", "title", "is_active"]


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


class DepartmentHeadForm(forms.ModelForm):
    class Meta:
        model = DepartmentHead
        fields = ["department", "staff", "start_date", "end_date", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }
