from django import forms

from apps.tenant.orgsettings.models import Campus

from .models import Applicant


class ApplicantForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = [
            "campus",
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "address",
            "target_term",
            "target_level",
            "target_program",
            "target_class_group",
            "status",
            "note",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        campuses = kwargs.pop("campuses", None)
        super().__init__(*args, **kwargs)
        if campuses is not None:
            self.fields["campus"].queryset = campuses
        else:
            self.fields["campus"].queryset = Campus.objects.all()
