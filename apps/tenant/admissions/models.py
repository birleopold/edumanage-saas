import secrets
import uuid

from django.conf import settings
from django.db import connection, models
from django.utils import timezone


def applicant_document_upload_to(instance, filename: str) -> str:
    schema = getattr(connection, "schema_name", "public") or "public"
    applicant_ref = getattr(instance.applicant, "application_reference", "") or f"applicant-{instance.applicant_id or 'new'}"
    safe_ref = str(applicant_ref).replace("/", "-").replace(" ", "-")
    return f"{schema}/admissions/{safe_ref}/{filename}"


class Applicant(models.Model):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"

    STATUS_CHOICES = (
        (NEW, "New"),
        (IN_REVIEW, "In review"),
        (ADMITTED, "Admitted"),
        (REJECTED, "Rejected"),
    )

    SOURCE_ADMIN = "ADMIN"
    SOURCE_ONLINE = "ONLINE"
    SOURCE_PHONE = "PHONE"
    SOURCE_WALK_IN = "WALK_IN"
    SOURCE_LEAD = "LEAD"

    SOURCE_CHOICES = (
        (SOURCE_ADMIN, "Admin entry"),
        (SOURCE_ONLINE, "Online application"),
        (SOURCE_PHONE, "Phone enquiry"),
        (SOURCE_WALK_IN, "Walk-in"),
        (SOURCE_LEAD, "Converted enquiry"),
    )

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    application_reference = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text="Public tracking reference generated when an application is submitted.",
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_relationship = models.CharField(max_length=80, blank=True)
    previous_school = models.CharField(max_length=180, blank=True)

    target_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_level = models.ForeignKey(
        "academics.Level",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_class_group = models.ForeignKey(
        "academics.ClassGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=NEW)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_ADMIN)
    submitted_online = models.BooleanField(default=False)

    custom_responses = models.JSONField(default=dict, blank=True)

    created_student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_admission_invoice = models.ForeignKey(
        "finance.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applicants",
        help_text="Student invoice automatically created during admission conversion, where applicable.",
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["submitted_online", "created_at"]),
        ]

    def __str__(self) -> str:
        ref = self.application_reference or f"#{self.pk or 'new'}"
        return f"{self.full_name()} ({ref})"

    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()

    def _generate_application_reference(self) -> str:
        while True:
            token = secrets.token_hex(4).upper()
            reference = f"APP-{token}"
            if not Applicant.objects.filter(application_reference=reference).exists():
                return reference

    def save(self, *args, **kwargs):
        if not self.application_reference:
            self.application_reference = self._generate_application_reference()
        super().save(*args, **kwargs)


class ApplicantDocument(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=120, default="Supporting document")
    file = models.FileField(upload_to=applicant_document_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return f"{self.applicant} - {self.title}"


class AdmissionLead(models.Model):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    FOLLOW_UP = "FOLLOW_UP"
    CONVERTED = "CONVERTED"
    LOST = "LOST"

    STATUS_CHOICES = (
        (NEW, "New lead"),
        (CONTACTED, "Contacted"),
        (FOLLOW_UP, "Follow-up"),
        (CONVERTED, "Converted to applicant"),
        (LOST, "Lost"),
    )

    SOURCE_WEBSITE = "WEBSITE"
    SOURCE_PHONE = "PHONE"
    SOURCE_WALK_IN = "WALK_IN"
    SOURCE_REFERRAL = "REFERRAL"
    SOURCE_SOCIAL = "SOCIAL"
    SOURCE_OTHER = "OTHER"

    SOURCE_CHOICES = (
        (SOURCE_WEBSITE, "Website"),
        (SOURCE_PHONE, "Phone"),
        (SOURCE_WALK_IN, "Walk-in"),
        (SOURCE_REFERRAL, "Referral"),
        (SOURCE_SOCIAL, "Social media"),
        (SOURCE_OTHER, "Other"),
    )

    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_WEBSITE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=NEW)

    learner_name = models.CharField(max_length=180)
    parent_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    interested_program = models.ForeignKey("academics.Program", on_delete=models.SET_NULL, null=True, blank=True)
    interested_class_group = models.ForeignKey("academics.ClassGroup", on_delete=models.SET_NULL, null=True, blank=True)

    follow_up_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    converted_applicant = models.ForeignKey(Applicant, on_delete=models.SET_NULL, null=True, blank=True, related_name="source_leads")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["follow_up_at"])]

    def __str__(self) -> str:
        return f"{self.learner_name} - {self.get_status_display()}"


class AdmissionAppointment(models.Model):
    INTERVIEW = "INTERVIEW"
    TEST = "TEST"
    MEETING = "MEETING"

    TYPE_CHOICES = (
        (INTERVIEW, "Interview"),
        (TEST, "Admission test"),
        (MEETING, "Parent meeting"),
    )

    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = (
        (SCHEDULED, "Scheduled"),
        (COMPLETED, "Completed"),
        (MISSED, "Missed"),
        (CANCELLED, "Cancelled"),
    )

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="appointments")
    appointment_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=INTERVIEW)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=SCHEDULED)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    location = models.CharField(max_length=180, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    outcome_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheduled_at",)
        indexes = [models.Index(fields=["status", "scheduled_at"])]

    def __str__(self) -> str:
        return f"{self.get_appointment_type_display()} for {self.applicant}"


class AdmissionFormTemplate(models.Model):
    name = models.CharField(max_length=160)
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    program = models.ForeignKey("academics.Program", on_delete=models.SET_NULL, null=True, blank=True)
    class_group = models.ForeignKey("academics.ClassGroup", on_delete=models.SET_NULL, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    admission_fee_item = models.ForeignKey("finance.FeeItem", on_delete=models.SET_NULL, null=True, blank=True)
    admission_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class AdmissionFormField(models.Model):
    TEXT = "TEXT"
    TEXTAREA = "TEXTAREA"
    NUMBER = "NUMBER"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"
    CHOICE = "CHOICE"

    FIELD_TYPE_CHOICES = (
        (TEXT, "Short text"),
        (TEXTAREA, "Long text"),
        (NUMBER, "Number"),
        (DATE, "Date"),
        (BOOLEAN, "Yes/No"),
        (CHOICE, "Choice"),
    )

    template = models.ForeignKey(AdmissionFormTemplate, on_delete=models.CASCADE, related_name="fields")
    label = models.CharField(max_length=160)
    field_type = models.CharField(max_length=16, choices=FIELD_TYPE_CHOICES, default=TEXT)
    help_text = models.CharField(max_length=255, blank=True)
    choices = models.TextField(blank=True, help_text="For choice fields, enter one option per line.")
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "label")

    def __str__(self) -> str:
        return self.label

    @property
    def form_key(self) -> str:
        return f"custom_{self.pk}"


class ApplicantCommunication(models.Model):
    CALL = "CALL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    NOTE = "NOTE"

    CHANNEL_CHOICES = (
        (CALL, "Phone call"),
        (SMS, "SMS"),
        (WHATSAPP, "WhatsApp"),
        (EMAIL, "Email"),
        (NOTE, "Internal note"),
    )

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="communications")
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default=NOTE)
    subject = models.CharField(max_length=160, blank=True)
    message = models.TextField()
    direction = models.CharField(max_length=16, choices=(("INBOUND", "Inbound"), ("OUTBOUND", "Outbound")), default="OUTBOUND")
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_channel_display()} - {self.applicant}"


class ApplicantPayment(models.Model):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    WAIVED = "WAIVED"

    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (PAID, "Paid"),
        (FAILED, "Failed"),
        (WAIVED, "Waived"),
    )

    CASH = "CASH"
    BANK = "BANK"
    MOBILE = "MOBILE"
    CARD = "CARD"

    METHOD_CHOICES = (
        (CASH, "Cash"),
        (BANK, "Bank"),
        (MOBILE, "Mobile money"),
        (CARD, "Card"),
    )

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="admission_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default=CASH)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PAID)
    reference = models.CharField(max_length=128, blank=True)
    received_at = models.DateField(default=timezone.localdate)
    note = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at", "-created_at")

    def __str__(self) -> str:
        return f"{self.applicant} - {self.amount} ({self.status})"
