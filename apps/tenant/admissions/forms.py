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
            "guardian_name",
            "guardian_relationship",
            "previous_school",
            "target_term",
            "target_level",
            "target_program",
            "target_class_group",
            "status",
            "source",
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


class PublicApplicantForm(forms.ModelForm):
    supporting_document = forms.FileField(
        required=False,
        help_text="Optional: upload a previous report, birth certificate, recommendation letter, or any supporting document.",
    )
    document_title = forms.CharField(
        required=False,
        max_length=120,
        initial="Supporting document",
        help_text="Example: Previous report, birth certificate, recommendation letter.",
    )

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
            "guardian_name",
            "guardian_relationship",
            "previous_school",
            "target_term",
            "target_level",
            "target_program",
            "target_class_group",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "email": "Used for admission updates where email is available.",
            "phone": "Used by the admissions office for follow-up.",
        }

    def __init__(self, *args, **kwargs):
        campuses = kwargs.pop("campuses", None)
        super().__init__(*args, **kwargs)
        if campuses is not None:
            self.fields["campus"].queryset = campuses
        else:
            self.fields["campus"].queryset = Campus.objects.all()

        self.fields["campus"].required = False
        self.fields["email"].required = False
        self.fields["phone"].required = True
        self.fields["guardian_name"].required = True
        self.fields["guardian_relationship"].required = True

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip()
        phone = (cleaned.get("phone") or "").strip()
        if not email and not phone:
            raise forms.ValidationError("Please provide at least a phone number or email address for follow-up.")
        return cleaned
