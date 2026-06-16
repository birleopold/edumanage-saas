from django import forms

from apps.tenant.academics.models import Stream
from apps.tenant.orgsettings.models import Campus
from apps.tenant.students.models import StudentProfile

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
            "address": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        campuses = kwargs.pop("campuses", None)
        super().__init__(*args, **kwargs)
        if campuses is not None:
            self.fields["campus"].queryset = campuses
        else:
            self.fields["campus"].queryset = Campus.objects.all()


class AdmissionDecisionForm(forms.Form):
    status = forms.ChoiceField(
        choices=(
            (Applicant.NEW, "New"),
            (Applicant.IN_REVIEW, "In review"),
            (Applicant.REJECTED, "Rejected"),
        )
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional internal note to add to the applicant record.",
    )


class ApplicantConversionForm(forms.Form):
    campus = forms.ModelChoiceField(
        queryset=Campus.objects.none(),
        required=True,
        help_text="Campus where the new student will be registered.",
    )
    stream = forms.ModelChoiceField(
        queryset=Stream.objects.none(),
        required=False,
        help_text="Optional class stream placement for the student.",
    )
    student_id = forms.CharField(
        required=False,
        max_length=64,
        help_text="Leave blank to generate the next student number automatically.",
    )
    create_student_login = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Create a student portal login if the applicant has an email address.",
    )
    create_parent_link = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Create or link a parent/guardian profile using the guardian details on the application.",
    )
    send_credentials_email = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Send temporary student login details by email when a login is created.",
    )

    def __init__(self, *args, applicant: Applicant | None = None, campuses=None, **kwargs):
        self.applicant = applicant
        super().__init__(*args, **kwargs)
        campus_qs = campuses if campuses is not None else Campus.objects.filter(is_active=True).order_by("name")
        self.fields["campus"].queryset = campus_qs
        self.fields["stream"].queryset = Stream.objects.select_related("class_group", "class_group__campus").filter(is_active=True).order_by("class_group__name", "name")

        if applicant:
            if applicant.campus_id:
                self.fields["campus"].initial = applicant.campus
            if applicant.target_class_group_id:
                self.fields["stream"].queryset = self.fields["stream"].queryset.filter(class_group=applicant.target_class_group)

    def clean_student_id(self):
        value = (self.cleaned_data.get("student_id") or "").strip()
        if value and StudentProfile.objects.filter(student_id__iexact=value).exists():
            raise forms.ValidationError("This student number is already in use.")
        return value

    def clean(self):
        cleaned = super().clean()
        campus = cleaned.get("campus")
        stream = cleaned.get("stream")
        create_login = cleaned.get("create_student_login")

        if stream and campus and stream.class_group.campus_id and stream.class_group.campus_id != campus.id:
            self.add_error("stream", "The selected stream does not belong to the selected campus.")

        if create_login and self.applicant and not self.applicant.email:
            self.add_error("create_student_login", "A student login requires an applicant email address.")

        return cleaned


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
