from django import forms
from django.utils import timezone

from apps.tenant.academics.models import Stream
from apps.tenant.finance.models import FeeItem
from apps.tenant.orgsettings.models import Campus
from apps.tenant.students.models import StudentProfile

from .models import (
    AdmissionAppointment,
    AdmissionFormField,
    AdmissionFormTemplate,
    AdmissionLead,
    Applicant,
    ApplicantCommunication,
    ApplicantPayment,
)


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
    campus = forms.ModelChoiceField(queryset=Campus.objects.none(), required=True)
    stream = forms.ModelChoiceField(queryset=Stream.objects.none(), required=False)
    student_id = forms.CharField(required=False, max_length=64)
    create_student_login = forms.BooleanField(required=False, initial=True)
    create_parent_link = forms.BooleanField(required=False, initial=True)
    send_credentials_email = forms.BooleanField(required=False, initial=True)
    create_admission_invoice = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Create a student invoice for the admission/application fee during conversion.",
    )
    admission_fee_item = forms.ModelChoiceField(queryset=FeeItem.objects.none(), required=False)
    admission_fee_amount = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2)
    invoice_due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, applicant: Applicant | None = None, campuses=None, **kwargs):
        self.applicant = applicant
        super().__init__(*args, **kwargs)
        campus_qs = campuses if campuses is not None else Campus.objects.filter(is_active=True).order_by("name")
        self.fields["campus"].queryset = campus_qs
        self.fields["stream"].queryset = Stream.objects.select_related("class_group", "class_group__campus").filter(is_active=True).order_by("class_group__name", "name")
        self.fields["admission_fee_item"].queryset = FeeItem.objects.filter(is_active=True).order_by("name")

        if applicant:
            if applicant.campus_id:
                self.fields["campus"].initial = applicant.campus
            if applicant.target_class_group_id:
                self.fields["stream"].queryset = self.fields["stream"].queryset.filter(class_group=applicant.target_class_group)
            if not applicant.email:
                self.fields["create_student_login"].initial = False
                self.fields["send_credentials_email"].initial = False
            template = resolve_admission_form_template(applicant)
            if template:
                self.fields["admission_fee_item"].initial = template.admission_fee_item
                self.fields["admission_fee_amount"].initial = template.admission_fee_amount

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
        create_invoice = cleaned.get("create_admission_invoice")
        fee_item = cleaned.get("admission_fee_item")
        fee_amount = cleaned.get("admission_fee_amount")

        if stream and campus and stream.class_group.campus_id and stream.class_group.campus_id != campus.id:
            self.add_error("stream", "The selected stream does not belong to the selected campus.")
        if create_login and self.applicant and not self.applicant.email:
            self.add_error("create_student_login", "A student login requires an applicant email address.")
        if create_invoice and not fee_item and not fee_amount:
            self.add_error("create_admission_invoice", "Select a fee item or enter an admission fee amount before creating an invoice.")
        return cleaned


class AdmissionLeadForm(forms.ModelForm):
    class Meta:
        model = AdmissionLead
        fields = [
            "campus",
            "source",
            "status",
            "learner_name",
            "parent_name",
            "email",
            "phone",
            "interested_program",
            "interested_class_group",
            "follow_up_at",
            "assigned_to",
            "notes",
        ]
        widgets = {
            "follow_up_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("email") and not cleaned.get("phone"):
            raise forms.ValidationError("A lead must have at least a phone number or email address.")
        return cleaned


class AdmissionAppointmentForm(forms.ModelForm):
    class Meta:
        model = AdmissionAppointment
        fields = ["appointment_type", "status", "scheduled_at", "duration_minutes", "location", "assigned_to", "score", "outcome_note"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "outcome_note": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        scheduled_at = cleaned.get("scheduled_at")
        duration = cleaned.get("duration_minutes")
        if duration is not None and duration <= 0:
            self.add_error("duration_minutes", "Duration must be greater than zero.")
        if scheduled_at and cleaned.get("status") == AdmissionAppointment.SCHEDULED and scheduled_at < timezone.now():
            self.add_error("scheduled_at", "Scheduled appointments cannot be in the past.")
        return cleaned


class ApplicantCommunicationForm(forms.ModelForm):
    class Meta:
        model = ApplicantCommunication
        fields = ["channel", "direction", "subject", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


class ApplicantPaymentForm(forms.ModelForm):
    class Meta:
        model = ApplicantPayment
        fields = ["amount", "method", "status", "reference", "received_at", "note"]
        widgets = {
            "received_at": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Payment amount must be greater than zero.")
        return amount


class AdmissionFormTemplateForm(forms.ModelForm):
    class Meta:
        model = AdmissionFormTemplate
        fields = ["name", "campus", "program", "class_group", "is_default", "is_active", "admission_fee_item", "admission_fee_amount"]


class AdmissionFormFieldForm(forms.ModelForm):
    class Meta:
        model = AdmissionFormField
        fields = ["label", "field_type", "help_text", "choices", "is_required", "order", "is_active"]
        widgets = {"choices": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("field_type") == AdmissionFormField.CHOICE and not (cleaned.get("choices") or "").strip():
            self.add_error("choices", "Choice fields require one option per line.")
        return cleaned


def resolve_admission_form_template(applicant_or_none=None, *, program=None, class_group=None, campus=None):
    qs = AdmissionFormTemplate.objects.filter(is_active=True).prefetch_related("fields")
    if applicant_or_none:
        program = applicant_or_none.target_program
        class_group = applicant_or_none.target_class_group
        campus = applicant_or_none.campus
    candidates = []
    if program and class_group and campus:
        candidates.append(qs.filter(program=program, class_group=class_group, campus=campus).first())
    if program and class_group:
        candidates.append(qs.filter(program=program, class_group=class_group, campus__isnull=True).first())
    if program:
        candidates.append(qs.filter(program=program, class_group__isnull=True).first())
    if class_group:
        candidates.append(qs.filter(program__isnull=True, class_group=class_group).first())
    if campus:
        candidates.append(qs.filter(campus=campus, program__isnull=True, class_group__isnull=True).first())
    candidates.append(qs.filter(is_default=True).first())
    candidates.append(qs.first())
    return next((item for item in candidates if item), None)


class PublicTrackingForm(forms.Form):
    reference = forms.CharField(max_length=32, label="Application reference")
    contact = forms.CharField(max_length=120, required=False, help_text="Optional phone or email used during application.")


class PublicApplicantForm(forms.ModelForm):
    supporting_document = forms.FileField(required=False)
    document_title = forms.CharField(required=False, max_length=120, initial="Supporting document")

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

    def __init__(self, *args, **kwargs):
        campuses = kwargs.pop("campuses", None)
        super().__init__(*args, **kwargs)
        self.dynamic_fields = []
        self.fields["campus"].queryset = campuses if campuses is not None else Campus.objects.all()
        self.fields["campus"].required = False
        self.fields["email"].required = False
        self.fields["phone"].required = True
        self.fields["guardian_name"].required = True
        self.fields["guardian_relationship"].required = True

        template = resolve_admission_form_template()
        self.template = template
        if template:
            for field in template.fields.filter(is_active=True):
                key = field.form_key
                options = {"label": field.label, "required": field.is_required, "help_text": field.help_text}
                if field.field_type == AdmissionFormField.TEXTAREA:
                    self.fields[key] = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **options)
                elif field.field_type == AdmissionFormField.NUMBER:
                    self.fields[key] = forms.DecimalField(**options)
                elif field.field_type == AdmissionFormField.DATE:
                    self.fields[key] = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **options)
                elif field.field_type == AdmissionFormField.BOOLEAN:
                    self.fields[key] = forms.BooleanField(required=False, label=field.label, help_text=field.help_text)
                elif field.field_type == AdmissionFormField.CHOICE:
                    choices = [(x.strip(), x.strip()) for x in field.choices.splitlines() if x.strip()]
                    self.fields[key] = forms.ChoiceField(choices=choices, **options)
                else:
                    self.fields[key] = forms.CharField(**options)
                self.dynamic_fields.append((field, key))

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip()
        phone = (cleaned.get("phone") or "").strip()
        if not email and not phone:
            raise forms.ValidationError("Please provide at least a phone number or email address for follow-up.")
        return cleaned

    def custom_responses(self):
        data = {}
        for field, key in self.dynamic_fields:
            value = self.cleaned_data.get(key)
            if value is not None and value != "":
                data[str(field.pk)] = {"label": field.label, "value": str(value)}
        return data
