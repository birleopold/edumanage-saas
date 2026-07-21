from django import forms

from apps.tenant.academics.models import AcademicTerm, Level, Program
from apps.tenant.education_frameworks.models import EducationStage
from apps.tenant.orgsettings.models import Campus
from apps.tenant.students.models import StudentProfile

from .clearance_models import ClearanceOverride, ClearancePolicy


class ClearancePolicyForm(forms.ModelForm):
    class Meta:
        model = ClearancePolicy
        fields = [
            "code",
            "name",
            "description",
            "access_type",
            "campus",
            "stage",
            "level",
            "program",
            "academic_term",
            "calculation_basis",
            "rule_type",
            "minimum_paid_percentage",
            "maximum_outstanding_balance",
            "allow_when_no_invoice",
            "enforcement_mode",
            "user_message",
            "priority",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["campus"].queryset = Campus.objects.order_by("name")
        self.fields["stage"].queryset = EducationStage.objects.filter(is_active=True).order_by("order", "name")
        self.fields["level"].queryset = Level.objects.filter(is_active=True).order_by("order", "name")
        self.fields["program"].queryset = Program.objects.filter(is_active=True).order_by("name")
        self.fields["academic_term"].queryset = AcademicTerm.objects.select_related("year").order_by("-year__name", "order")


class ClearanceOverrideForm(forms.ModelForm):
    class Meta:
        model = ClearanceOverride
        fields = [
            "student",
            "policy",
            "access_type",
            "academic_term",
            "valid_from",
            "valid_until",
            "reason",
            "reference",
            "is_active",
        ]
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = StudentProfile.objects.filter(is_active=True).select_related("campus", "stream").order_by("last_name", "first_name")
        self.fields["policy"].queryset = ClearancePolicy.objects.filter(is_active=True).order_by("-priority", "name")
        self.fields["academic_term"].queryset = AcademicTerm.objects.select_related("year").order_by("-year__name", "order")


class ClearanceCheckForm(forms.Form):
    student = forms.ModelChoiceField(queryset=StudentProfile.objects.none())
    access_type = forms.ChoiceField(choices=ClearancePolicy.ACCESS_TYPE_CHOICES)
    academic_term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.none(),
        required=False,
        help_text="Leave blank to use the current academic term.",
    )
    record_decision = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = StudentProfile.objects.filter(is_active=True).select_related("campus", "stream", "stream__class_group").order_by("last_name", "first_name")
        self.fields["academic_term"].queryset = AcademicTerm.objects.select_related("year").order_by("-year__name", "order")
