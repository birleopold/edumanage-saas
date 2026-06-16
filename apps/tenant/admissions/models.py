import secrets
import uuid

from django.db import connection, models


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

    SOURCE_CHOICES = (
        (SOURCE_ADMIN, "Admin entry"),
        (SOURCE_ONLINE, "Online application"),
        (SOURCE_PHONE, "Phone enquiry"),
        (SOURCE_WALK_IN, "Walk-in"),
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

    created_student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
