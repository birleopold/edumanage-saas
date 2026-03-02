from django import forms

from apps.tenant.students.models import StudentProfile

from .models import ParentProfile, ParentStudentLink


class ParentProfileForm(forms.ModelForm):
    create_user = forms.BooleanField(required=False, initial=True)
    send_email = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = ParentProfile
        fields = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "is_active",
        ]


class ParentStudentLinkForm(forms.ModelForm):
    student = forms.ModelChoiceField(queryset=StudentProfile.objects.all())

    class Meta:
        model = ParentStudentLink
        fields = [
            "student",
            "relationship",
            "is_primary",
        ]
