from django import forms

from apps.tenant.students.models import StudentProfile

from .forms import ParentProfileForm


class ParentCreateForm(ParentProfileForm):
    student = forms.ModelChoiceField(
        label="Student cared for",
        queryset=StudentProfile.objects.filter(is_active=True).select_related("campus", "stream"),
        help_text="Select the learner this parent or guardian is responsible for.",
    )
    relationship = forms.CharField(
        label="Relationship to student",
        max_length=64,
        help_text="For example: Mother, Father, Guardian, Aunt, Uncle or Sponsor.",
    )
    is_primary_guardian = forms.BooleanField(
        label="Primary guardian",
        required=False,
        initial=True,
        help_text="Use this parent first for urgent communication about the selected student.",
    )

    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = self.fields["student"].queryset
        if campus_scope is not None:
            queryset = queryset.filter(campus=campus_scope)
        self.fields["student"].queryset = queryset.order_by("last_name", "first_name", "student_id")
