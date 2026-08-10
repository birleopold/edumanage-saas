from __future__ import annotations

import secrets
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.utils import timezone
from django.utils.text import get_valid_filename

from .schema import validate_design_document


def _tenant_prefix() -> str:
    return getattr(connection, "schema_name", "public") or "public"


def design_background_upload_to(instance, filename: str) -> str:
    safe = get_valid_filename(Path(filename).name) or "background"
    return f"{_tenant_prefix()}/design-studio/backgrounds/{instance.template_id or 'draft'}/{uuid4().hex}-{safe}"


def issued_document_upload_to(instance, filename: str) -> str:
    safe = get_valid_filename(Path(filename).name) or "document.pdf"
    return f"{_tenant_prefix()}/design-studio/issued/{timezone.localdate():%Y/%m}/{instance.reference}/{safe}"


def verification_token() -> str:
    return secrets.token_urlsafe(24)


class DocumentTemplate(models.Model):
    STUDENT_ID = "STUDENT_ID"
    REPORT_CARD = "REPORT_CARD"
    TRANSCRIPT = "TRANSCRIPT"
    LEAVERS_CERTIFICATE = "LEAVERS_CERTIFICATE"
    ADMISSION_LETTER = "ADMISSION_LETTER"
    EXAM_PERMIT = "EXAM_PERMIT"
    CERTIFICATE = "CERTIFICATE"
    CUSTOM = "CUSTOM"
    DOCUMENT_TYPE_CHOICES = (
        (STUDENT_ID, "Student ID card"),
        (REPORT_CARD, "End-of-term report card"),
        (TRANSCRIPT, "Academic transcript"),
        (LEAVERS_CERTIFICATE, "Leavers certificate"),
        (ADMISSION_LETTER, "Admission letter"),
        (EXAM_PERMIT, "Examination permit"),
        (CERTIFICATE, "Certificate"),
        (CUSTOM, "Custom document"),
    )

    name = models.CharField(max_length=160)
    document_type = models.CharField(max_length=32, choices=DOCUMENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.CASCADE, null=True, blank=True, related_name="document_templates")
    stage = models.ForeignKey("education_frameworks.EducationStage", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_templates")
    level = models.ForeignKey("academics.Level", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_templates")
    active_version_number = models.PositiveIntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_document_templates")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_document_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("document_type", "-is_default", "name")
        constraints = [
            models.UniqueConstraint(fields=("campus", "stage", "level", "document_type", "name"), name="uniq_design_template_scope_name"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def active_version(self):
        if not self.active_version_number:
            return None
        return self.versions.filter(number=self.active_version_number, status=DocumentTemplateVersion.ACTIVE).first()

    @property
    def latest_version(self):
        return self.versions.order_by("-number").first()

    def clean(self):
        if self.is_default and self.is_active:
            duplicate = type(self).objects.filter(
                campus_id=self.campus_id,
                stage_id=self.stage_id,
                level_id=self.level_id,
                document_type=self.document_type,
                is_default=True,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError({"is_default": "This scope already has an active default design for this document type."})


class DocumentTemplateVersion(models.Model):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (IN_REVIEW, "In review"),
        (APPROVED, "Approved"),
        (ACTIVE, "Active"),
        (ARCHIVED, "Archived"),
    )
    FIT_COVER = "COVER"
    FIT_CONTAIN = "CONTAIN"
    FIT_STRETCH = "STRETCH"
    BACKGROUND_FIT_CHOICES = (
        (FIT_COVER, "Cover"),
        (FIT_CONTAIN, "Contain"),
        (FIT_STRETCH, "Stretch"),
    )

    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    design = models.JSONField(default=dict)
    page_width_mm = models.DecimalField(max_digits=7, decimal_places=2, default=210)
    page_height_mm = models.DecimalField(max_digits=7, decimal_places=2, default=297)
    background = models.ImageField(upload_to=design_background_upload_to, blank=True)
    background_fit = models.CharField(max_length=12, choices=BACKGROUND_FIT_CHOICES, default=FIT_COVER)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_document_template_versions")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_document_template_versions")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_document_template_versions")
    approved_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activated_document_template_versions")
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("template", "-number")
        constraints = [models.UniqueConstraint(fields=("template", "number"), name="uniq_design_template_version")]

    def __str__(self) -> str:
        return f"{self.template.name} v{self.number}"

    @property
    def is_locked(self) -> bool:
        return self.status in {self.APPROVED, self.ACTIVE, self.ARCHIVED}

    def clean(self):
        width = float(self.page_width_mm or 0)
        height = float(self.page_height_mm or 0)
        if not 25 <= width <= 1000:
            raise ValidationError({"page_width_mm": "Page width must be between 25 mm and 1000 mm."})
        if not 25 <= height <= 1000:
            raise ValidationError({"page_height_mm": "Page height must be between 25 mm and 1000 mm."})
        validate_design_document(self.design or {}, width, height)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status", "design", "page_width_mm", "page_height_mm", "background", "background_fit").first()
            if previous and previous["status"] in {self.APPROVED, self.ACTIVE, self.ARCHIVED}:
                protected_changed = (
                    previous["design"] != self.design
                    or previous["page_width_mm"] != self.page_width_mm
                    or previous["page_height_mm"] != self.page_height_mm
                    or str(previous["background"] or "") != str(self.background.name or "")
                    or previous["background_fit"] != self.background_fit
                )
                if protected_changed:
                    raise ValidationError("Approved, active and archived versions are immutable. Create a new draft version instead.")
        self.full_clean()
        return super().save(*args, **kwargs)


class IssuedDocument(models.Model):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    STATUS_CHOICES = ((ACTIVE, "Active"), (REVOKED, "Revoked"))

    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT, related_name="issued_documents")
    version = models.ForeignKey(DocumentTemplateVersion, on_delete=models.PROTECT, related_name="issued_documents")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.PROTECT, related_name="designed_documents")
    academic_term = models.ForeignKey("academics.AcademicTerm", on_delete=models.SET_NULL, null=True, blank=True, related_name="designed_documents")
    reference = models.CharField(max_length=80, unique=True)
    verification_token = models.CharField(max_length=80, unique=True, default=verification_token, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=ACTIVE)
    data_snapshot = models.JSONField(default=dict)
    pdf_file = models.FileField(upload_to=issued_document_upload_to, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_designed_documents")
    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="revoked_designed_documents")
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-issued_at",)
        indexes = [models.Index(fields=("verification_token", "status"), name="designstudio_verify_idx")]

    def __str__(self) -> str:
        return self.reference

    @property
    def is_valid(self) -> bool:
        return self.status == self.ACTIVE
