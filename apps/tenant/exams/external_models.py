import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def normalize_external_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", str(value or "").strip().upper()).strip("-")


class ExternalExamBoard(models.Model):
    NATIONAL = "NATIONAL"
    REGIONAL = "REGIONAL"
    INTERNATIONAL = "INTERNATIONAL"
    PROFESSIONAL = "PROFESSIONAL"
    OTHER = "OTHER"

    BOARD_TYPE_CHOICES = (
        (NATIONAL, "National examination board"),
        (REGIONAL, "Regional examination board"),
        (INTERNATIONAL, "International examination board"),
        (PROFESSIONAL, "Professional examination body"),
        (OTHER, "Other external body"),
    )

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    board_type = models.CharField(max_length=24, choices=BOARD_TYPE_CHOICES, default=NATIONAL)
    country_code = models.CharField(max_length=2, blank=True)
    website = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    candidate_number_label = models.CharField(max_length=64, default="Candidate number")
    subject_code_label = models.CharField(max_length=64, default="Subject code")
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = normalize_external_code(self.code)
        self.country_code = str(self.country_code or "").strip().upper()
        super().save(*args, **kwargs)


class ExternalExamCentre(models.Model):
    board = models.ForeignKey(ExternalExamBoard, on_delete=models.PROTECT, related_name="centres")
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_exam_centres",
    )
    code = models.CharField(max_length=48)
    name = models.CharField(max_length=128)
    address = models.TextField(blank=True)
    contact_name = models.CharField(max_length=128, blank=True)
    contact_phone = models.CharField(max_length=48, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("board__name", "code")
        constraints = [
            models.UniqueConstraint(fields=("board", "code"), name="uniq_ext_board_centre_code")
        ]

    def __str__(self) -> str:
        return f"{self.board.code} {self.code} — {self.name}"

    def clean(self):
        super().clean()
        if self.board_id and not self.board.is_active and self.is_active:
            raise ValidationError({"board": "An active centre must belong to an active examination board."})

    def save(self, *args, **kwargs):
        self.code = normalize_external_code(self.code)
        super().save(*args, **kwargs)


class ExternalExamSession(models.Model):
    DRAFT = "DRAFT"
    REGISTRATION_OPEN = "REGISTRATION_OPEN"
    REGISTRATION_CLOSED = "REGISTRATION_CLOSED"
    RESULTS_PENDING = "RESULTS_PENDING"
    RESULTS_RELEASED = "RESULTS_RELEASED"
    ARCHIVED = "ARCHIVED"

    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (REGISTRATION_OPEN, "Registration open"),
        (REGISTRATION_CLOSED, "Registration closed"),
        (RESULTS_PENDING, "Results pending"),
        (RESULTS_RELEASED, "Results released"),
        (ARCHIVED, "Archived"),
    )

    board = models.ForeignKey(ExternalExamBoard, on_delete=models.PROTECT, related_name="sessions")
    centre = models.ForeignKey(
        ExternalExamCentre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    code = models.CharField(max_length=48)
    name = models.CharField(max_length=128)
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        related_name="external_exam_sessions",
    )
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_exam_sessions",
    )
    stage = models.ForeignKey(
        "education_frameworks.EducationStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_exam_sessions",
    )
    level = models.ForeignKey(
        "academics.Level",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_exam_sessions",
    )
    program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_exam_sessions",
    )
    linked_exam = models.ForeignKey(
        "exams.Exam",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_sessions",
        help_text="Optional compatibility link. Internal exam papers and scores remain authoritative.",
    )
    registration_opens = models.DateField(null=True, blank=True)
    registration_closes = models.DateField(null=True, blank=True)
    exam_starts = models.DateField(null=True, blank=True)
    exam_ends = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=DRAFT)
    candidate_prefix = models.CharField(max_length=32, blank=True)
    candidate_number_padding = models.PositiveSmallIntegerField(default=4)
    next_candidate_sequence = models.PositiveIntegerField(default=1)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-academic_year__name", "board__name", "name")
        constraints = [
            models.UniqueConstraint(fields=("board", "code"), name="uniq_ext_board_session_code")
        ]

    def __str__(self) -> str:
        return f"{self.board.code} {self.code} — {self.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.board_id and not self.board.is_active and self.is_active:
            errors["board"] = "An active session must use an active examination board."
        if self.centre_id and self.board_id and self.centre.board_id != self.board_id:
            errors["centre"] = "The examination centre must belong to the selected board."
        if self.centre_id and self.campus_id and self.centre.campus_id and self.centre.campus_id != self.campus_id:
            errors["campus"] = "The session campus must match the examination centre campus."
        if self.linked_exam_id and self.academic_year_id and self.linked_exam.term.year_id != self.academic_year_id:
            errors["linked_exam"] = "The linked internal exam must belong to the selected academic year."
        if self.registration_opens and self.registration_closes and self.registration_closes < self.registration_opens:
            errors["registration_closes"] = "Registration closing date cannot be before the opening date."
        if self.exam_starts and self.exam_ends and self.exam_ends < self.exam_starts:
            errors["exam_ends"] = "Exam ending date cannot be before the starting date."
        if self.registration_closes and self.exam_starts and self.exam_starts < self.registration_closes:
            errors["exam_starts"] = "Exam dates cannot start before candidate registration closes."
        if self.candidate_number_padding < 1 or self.candidate_number_padding > 12:
            errors["candidate_number_padding"] = "Candidate number padding must be between 1 and 12."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = normalize_external_code(self.code)
        self.candidate_prefix = str(self.candidate_prefix or "").strip().upper()
        super().save(*args, **kwargs)

    @property
    def registration_is_open(self) -> bool:
        today = timezone.localdate()
        if self.status != self.REGISTRATION_OPEN or not self.is_active:
            return False
        if self.registration_opens and today < self.registration_opens:
            return False
        if self.registration_closes and today > self.registration_closes:
            return False
        return True

    @property
    def scope_label(self) -> str:
        parts = []
        for value in (self.campus, self.stage, self.level, self.program):
            if value:
                parts.append(str(value))
        return " · ".join(parts) if parts else "Institution-wide"


class ExternalExamSubject(models.Model):
    session = models.ForeignKey(ExternalExamSession, on_delete=models.CASCADE, related_name="subjects")
    course = models.ForeignKey(
        "academics.Course",
        on_delete=models.PROTECT,
        related_name="external_exam_subjects",
    )
    subject_code = models.CharField(max_length=48)
    display_name = models.CharField(max_length=128, blank=True)
    linked_paper = models.ForeignKey(
        "exams.ExamPaper",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_subjects",
        help_text="Optional compatibility link. Existing exam scores are not copied.",
    )
    max_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_compulsory = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("session", "order", "course__name")
        constraints = [
            models.UniqueConstraint(fields=("session", "course"), name="uniq_ext_session_course"),
            models.UniqueConstraint(fields=("session", "subject_code"), name="uniq_ext_session_subject_code"),
        ]

    def __str__(self) -> str:
        return f"{self.session.code} {self.subject_code} — {self.display_title}"

    @property
    def display_title(self) -> str:
        return self.display_name or self.course.name

    def clean(self):
        super().clean()
        errors = {}
        if self.course_id and not self.course.is_active and self.is_active:
            errors["course"] = "An active external subject must use an active course."
        if self.linked_paper_id:
            if self.linked_paper.offering.course_id != self.course_id:
                errors["linked_paper"] = "The linked paper must use the selected course."
            if self.session.linked_exam_id and self.linked_paper.exam_id != self.session.linked_exam_id:
                errors["linked_paper"] = "The linked paper must belong to the session's linked internal exam."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.subject_code = normalize_external_code(self.subject_code)
        super().save(*args, **kwargs)


class ExternalCandidate(models.Model):
    DRAFT = "DRAFT"
    REGISTERED = "REGISTERED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    WITHDRAWN = "WITHDRAWN"

    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (REGISTERED, "Registered"),
        (SUBMITTED, "Submitted to board"),
        (APPROVED, "Approved by board"),
        (WITHDRAWN, "Withdrawn"),
    )

    session = models.ForeignKey(ExternalExamSession, on_delete=models.CASCADE, related_name="candidates")
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.PROTECT,
        related_name="external_exam_candidates",
    )
    centre = models.ForeignKey(
        ExternalExamCentre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidates",
    )
    candidate_number = models.CharField(max_length=64)
    board_reference = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=REGISTERED)
    registration_date = models.DateField(default=timezone.localdate)
    accommodations = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("session", "candidate_number")
        constraints = [
            models.UniqueConstraint(fields=("session", "student"), name="uniq_ext_session_student"),
            models.UniqueConstraint(fields=("session", "candidate_number"), name="uniq_ext_session_candidate_no"),
        ]

    def __str__(self) -> str:
        return f"{self.candidate_number} — {self.student}"

    def clean(self):
        super().clean()
        errors = {}
        if self.centre_id and self.centre.board_id != self.session.board_id:
            errors["centre"] = "The candidate centre must belong to the session board."
        if self.session.campus_id and self.student.campus_id != self.session.campus_id:
            errors["student"] = "The learner must belong to the session campus."
        if self.centre_id and self.centre.campus_id and self.student.campus_id != self.centre.campus_id:
            errors["centre"] = "The learner campus must match the examination centre campus."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.candidate_number = str(self.candidate_number or "").strip().upper()
        self.board_reference = str(self.board_reference or "").strip()
        super().save(*args, **kwargs)


class ExternalCandidateSubject(models.Model):
    REGISTERED = "REGISTERED"
    WITHDRAWN = "WITHDRAWN"
    ABSENT = "ABSENT"
    EXEMPT = "EXEMPT"

    STATUS_CHOICES = (
        (REGISTERED, "Registered"),
        (WITHDRAWN, "Withdrawn"),
        (ABSENT, "Absent"),
        (EXEMPT, "Exempt"),
    )

    candidate = models.ForeignKey(ExternalCandidate, on_delete=models.CASCADE, related_name="subject_registrations")
    subject = models.ForeignKey(ExternalExamSubject, on_delete=models.PROTECT, related_name="candidate_registrations")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=REGISTERED)
    paper_reference = models.CharField(max_length=64, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("candidate", "subject__order", "subject__course__name")
        constraints = [
            models.UniqueConstraint(fields=("candidate", "subject"), name="uniq_ext_candidate_subject")
        ]

    def __str__(self) -> str:
        return f"{self.candidate.candidate_number} — {self.subject.subject_code}"

    def clean(self):
        super().clean()
        if self.candidate_id and self.subject_id and self.candidate.session_id != self.subject.session_id:
            raise ValidationError({"subject": "The subject must belong to the candidate's examination session."})


class ExternalExamResult(models.Model):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    ABSENT = "ABSENT"
    WITHHELD = "WITHHELD"
    EXEMPT = "EXEMPT"

    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (PASS, "Pass"),
        (FAIL, "Fail"),
        (ABSENT, "Absent"),
        (WITHHELD, "Withheld"),
        (EXEMPT, "Exempt"),
    )

    candidate_subject = models.OneToOneField(
        ExternalCandidateSubject,
        on_delete=models.CASCADE,
        related_name="official_result",
    )
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    grade = models.CharField(max_length=16, blank=True)
    result_status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    source_reference = models.CharField(max_length=128, blank=True)
    linked_exam_score = models.OneToOneField(
        "exams.ExamScore",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_result",
        help_text="Optional compatibility link. The internal exam score remains unchanged.",
    )
    is_official = models.BooleanField(default=True)
    released_at = models.DateTimeField(null=True, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_exam_results_imported",
    )
    raw_data = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("candidate_subject__candidate__candidate_number", "candidate_subject__subject__order")

    def __str__(self) -> str:
        return f"{self.candidate_subject} — {self.grade or self.result_status}"

    def clean(self):
        super().clean()
        errors = {}
        if self.percentage is not None and not Decimal("0") <= self.percentage <= Decimal("100"):
            errors["percentage"] = "Percentage must be between 0 and 100."
        if self.linked_exam_score_id:
            registration = self.candidate_subject
            if self.linked_exam_score.student_id != registration.candidate.student_id:
                errors["linked_exam_score"] = "The linked internal score must belong to the same learner."
            linked_paper_id = registration.subject.linked_paper_id
            if linked_paper_id and self.linked_exam_score.paper_id != linked_paper_id:
                errors["linked_exam_score"] = "The linked internal score must belong to the subject's linked paper."
        if errors:
            raise ValidationError(errors)


class ExternalResultImportBatch(models.Model):
    session = models.ForeignKey(ExternalExamSession, on_delete=models.CASCADE, related_name="result_import_batches")
    file_name = models.CharField(max_length=255)
    dry_run = models.BooleanField(default=True)
    row_count = models.PositiveIntegerField(default=0)
    accepted_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_result_import_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        mode = "dry run" if self.dry_run else "import"
        return f"{self.session.code} — {self.file_name} ({mode})"
