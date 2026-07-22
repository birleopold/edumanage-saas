import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def _token() -> str:
    return secrets.token_urlsafe(24)


class ReportTemplate(models.Model):
    """Institution-configurable report-card/transcript presentation policy."""

    name = models.CharField(max_length=160)
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    stage = models.ForeignKey("education_frameworks.EducationStage", on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey("academics.Level", on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=160, default="Learner Progress Report")
    sections = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered section keys, for example identity, results, attendance, ecd, activities, finance, comments and signatures.",
    )
    settings = models.JSONField(default=dict, blank=True)
    show_position = models.BooleanField(default=False)
    show_attendance = models.BooleanField(default=True)
    show_clearance = models.BooleanField(default=False)
    show_photo = models.BooleanField(default=True)
    show_verification_code = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_default", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("campus", "stage", "level", "name"),
                name="uniq_institutional_report_template_scope_name",
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        allowed = {"identity", "results", "attendance", "ecd", "activities", "finance", "comments", "signatures"}
        unknown = [item for item in (self.sections or []) if item not in allowed]
        if unknown:
            raise ValidationError({"sections": f"Unknown report sections: {', '.join(unknown)}"})
        if self.is_default and self.is_active:
            duplicate = type(self).objects.filter(
                campus_id=self.campus_id,
                stage_id=self.stage_id,
                level_id=self.level_id,
                is_default=True,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError({"is_default": "This scope already has an active default report template."})


class ResultPolicy(models.Model):
    GENERIC = "GENERIC"
    ECD = "ECD"
    PLE = "PLE"
    UCE = "UCE"
    UACE = "UACE"
    GPA = "GPA"
    SYSTEM_CHOICES = (
        (GENERIC, "Percentage and grade"),
        (ECD, "ECD developmental assessment"),
        (PLE, "PLE aggregate and division"),
        (UCE, "UCE aggregate or competency summary"),
        (UACE, "UACE principal/subsidiary points"),
        (GPA, "GPA and cumulative GPA"),
    )

    name = models.CharField(max_length=160)
    result_system = models.CharField(max_length=16, choices=SYSTEM_CHOICES, default=GENERIC)
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    stage = models.ForeignKey("education_frameworks.EducationStage", on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey("academics.Level", on_delete=models.SET_NULL, null=True, blank=True)
    program = models.ForeignKey("academics.Program", on_delete=models.SET_NULL, null=True, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    priority = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority", "-is_default", "name")

    def __str__(self):
        return self.name


class ECDObservation(models.Model):
    LANGUAGE = "LANGUAGE"
    SOCIAL = "SOCIAL"
    MOTOR = "MOTOR"
    NUMERACY = "NUMERACY"
    FEEDING = "FEEDING"
    ATTENDANCE = "ATTENDANCE"
    HYGIENE = "HYGIENE"
    EMOTIONAL = "EMOTIONAL"
    CREATIVITY = "CREATIVITY"
    DOMAIN_CHOICES = (
        (LANGUAGE, "Language development"),
        (SOCIAL, "Social behaviour"),
        (MOTOR, "Motor skills"),
        (NUMERACY, "Early numeracy"),
        (FEEDING, "Feeding"),
        (ATTENDANCE, "Attendance habits"),
        (HYGIENE, "Personal hygiene"),
        (EMOTIONAL, "Emotional development"),
        (CREATIVITY, "Creativity"),
    )
    ACHIEVED = "ACHIEVED"
    DEVELOPING = "DEVELOPING"
    NEEDS_SUPPORT = "NEEDS_SUPPORT"
    NOT_ASSESSED = "NOT_ASSESSED"
    RATING_CHOICES = (
        (ACHIEVED, "Achieved"),
        (DEVELOPING, "Developing"),
        (NEEDS_SUPPORT, "Needs support"),
        (NOT_ASSESSED, "Not yet assessed"),
    )

    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="ecd_observations")
    academic_term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE, related_name="ecd_observations")
    domain = models.CharField(max_length=24, choices=DOMAIN_CHOICES)
    rating = models.CharField(max_length=24, choices=RATING_CHOICES, default=NOT_ASSESSED)
    observation = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    observed_on = models.DateField(default=timezone.localdate)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "domain")
        constraints = [
            models.UniqueConstraint(fields=("student", "academic_term", "domain"), name="uniq_ecd_term_domain")
        ]

    def __str__(self):
        return f"{self.student} — {self.get_domain_display()}"


class LearnerSubjectCombination(models.Model):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="subject_combination_registrations")
    combination = models.ForeignKey("academics.SubjectCombination", on_delete=models.PROTECT, related_name="learner_registrations")
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.PROTECT, related_name="subject_combination_registrations")
    registered_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ("-academic_year__name", "student__last_name")
        constraints = [
            models.UniqueConstraint(fields=("student", "academic_year"), name="uniq_learner_combination_per_year")
        ]

    def __str__(self):
        return f"{self.student} — {self.combination}"

    def clean(self):
        errors = {}
        if self.student_id and self.combination_id:
            pathway = self.combination.pathway
            if pathway.campus_id and pathway.campus_id != self.student.campus_id:
                errors["combination"] = "The subject combination belongs to another campus."
            learner_level_id = getattr(getattr(self.student, "stream", None), "class_group", None)
            learner_level_id = getattr(learner_level_id, "level_id", None)
            if self.combination.level_id and learner_level_id and self.combination.level_id != learner_level_id:
                errors["combination"] = "The subject combination does not apply to the learner's current level."
            capacity = (self.combination.settings or {}).get("capacity")
            if capacity:
                used = type(self).objects.filter(combination=self.combination, academic_year=self.academic_year, is_active=True)
                if self.pk:
                    used = used.exclude(pk=self.pk)
                if used.count() >= int(capacity):
                    errors["combination"] = "The subject combination has reached its configured capacity."
        if errors:
            raise ValidationError(errors)


class CandidateDossier(models.Model):
    DRAFT = "DRAFT"
    READY = "READY"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    WITHDRAWN = "WITHDRAWN"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (READY, "Ready for submission"),
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (WITHDRAWN, "Withdrawn"),
    )

    student = models.ForeignKey("students.StudentProfile", on_delete=models.PROTECT, related_name="candidate_dossiers")
    external_session = models.ForeignKey("exams.ExternalExamSession", on_delete=models.CASCADE, related_name="candidate_dossiers")
    candidate_number = models.CharField(max_length=64)
    photograph = models.ImageField(upload_to="candidate_photos/%Y/%m/", blank=True)
    checklist = models.JSONField(default=dict, blank=True)
    continuous_assessment_complete = models.BooleanField(default=False)
    registration_status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    registration_reference = models.CharField(max_length=128, blank=True)
    verification_token = models.CharField(max_length=64, default=_token, unique=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("external_session", "candidate_number")
        constraints = [
            models.UniqueConstraint(fields=("student", "external_session"), name="uniq_candidate_dossier_session_student"),
            models.UniqueConstraint(fields=("external_session", "candidate_number"), name="uniq_candidate_dossier_number"),
        ]

    def __str__(self):
        return f"{self.candidate_number} — {self.student}"

    @property
    def checklist_complete(self):
        values = list((self.checklist or {}).values())
        return bool(values) and all(bool(value) for value in values)

    def clean(self):
        if self.student_id and self.external_session_id:
            if self.external_session.campus_id and self.external_session.campus_id != self.student.campus_id:
                raise ValidationError({"student": "The learner belongs to another campus."})
        if self.registration_status in {self.READY, self.SUBMITTED, self.APPROVED}:
            errors = {}
            if not self.photograph:
                errors["photograph"] = "Upload the candidate photograph before marking the dossier ready."
            if not self.checklist_complete:
                errors["checklist"] = "Complete every required candidate document before marking the dossier ready."
            if not self.continuous_assessment_complete:
                errors["continuous_assessment_complete"] = "Complete continuous assessment before marking the dossier ready."
            if errors:
                raise ValidationError(errors)


class CandidateMockCycle(models.Model):
    dossier = models.ForeignKey(CandidateDossier, on_delete=models.CASCADE, related_name="mock_cycles")
    name = models.CharField(max_length=128)
    exam_date = models.DateField()
    aggregate = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    division = models.CharField(max_length=32, blank=True)
    points = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    mean_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("dossier", "exam_date")
        constraints = [models.UniqueConstraint(fields=("dossier", "name"), name="uniq_candidate_mock_cycle")]

    def __str__(self):
        return f"{self.dossier} — {self.name}"


class CandidateExamAttendance(models.Model):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"
    STATUS_CHOICES = ((PRESENT, "Present"), (ABSENT, "Absent"), (LATE, "Late"), (EXCUSED, "Excused"))

    dossier = models.ForeignKey(CandidateDossier, on_delete=models.CASCADE, related_name="exam_attendance")
    subject_registration = models.ForeignKey("exams.ExternalCandidateSubject", on_delete=models.PROTECT, related_name="attendance_records")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PRESENT)
    marked_at = models.DateTimeField(default=timezone.now)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("dossier", "subject_registration__subject__order")
        constraints = [models.UniqueConstraint(fields=("dossier", "subject_registration"), name="uniq_candidate_subject_attendance")]

    def clean(self):
        if self.dossier_id and self.subject_registration_id:
            if self.subject_registration.candidate.student_id != self.dossier.student_id:
                raise ValidationError({"subject_registration": "The subject registration belongs to another learner."})
            if self.subject_registration.candidate.session_id != self.dossier.external_session_id:
                raise ValidationError({"subject_registration": "The subject registration belongs to another examination session."})


class VerifiablePermit(models.Model):
    CANDIDATE = "CANDIDATE"
    CLEARANCE = "CLEARANCE"
    GATE = "GATE"
    TRANSCRIPT = "TRANSCRIPT"
    REPORT = "REPORT"
    TYPE_CHOICES = (
        (CANDIDATE, "Candidate permit"),
        (CLEARANCE, "Assessment clearance permit"),
        (GATE, "Gate pass"),
        (TRANSCRIPT, "Academic transcript"),
        (REPORT, "Report card"),
    )
    ACTIVE = "ACTIVE"
    USED = "USED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    STATUS_CHOICES = ((ACTIVE, "Active"), (USED, "Used"), (REVOKED, "Revoked"), (EXPIRED, "Expired"))

    permit_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="verifiable_permits")
    title = models.CharField(max_length=160)
    reference = models.CharField(max_length=64, unique=True)
    verification_token = models.CharField(max_length=64, default=_token, unique=True, editable=False)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    metadata = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-issued_at",)
        indexes = [models.Index(fields=("verification_token", "status"), name="institution_verifi_e4b2c4_idx")]

    def __str__(self):
        return f"{self.reference} — {self.student}"

    @property
    def is_valid(self):
        now = timezone.now()
        return self.status == self.ACTIVE and self.valid_from <= now and (not self.valid_until or self.valid_until >= now)

    def clean(self):
        if self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "The expiry time must be after the start time."})


class VisitationWindow(models.Model):
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.CASCADE, related_name="visitation_windows")
    name = models.CharField(max_length=128)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    visitor_limit_per_student = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)

    class Meta:
        ordering = ("-starts_at",)
        constraints = [models.UniqueConstraint(fields=("campus", "name", "starts_at"), name="uniq_campus_visitation_window")]

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The end time must be after the start time."})

    def __str__(self):
        return f"{self.name} — {self.campus}"


class VisitorRecord(models.Model):
    visitation_window = models.ForeignKey(VisitationWindow, on_delete=models.SET_NULL, null=True, blank=True, related_name="visitors")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="visitor_records")
    visitor_name = models.CharField(max_length=160)
    identity_type = models.CharField(max_length=64)
    identity_number = models.CharField(max_length=96)
    phone = models.CharField(max_length=32, blank=True)
    relationship = models.CharField(max_length=64)
    purpose = models.CharField(max_length=160, blank=True)
    arrived_at = models.DateTimeField(default=timezone.now)
    departed_at = models.DateTimeField(null=True, blank=True)
    collected_student = models.BooleanField(default=False)
    student_returned_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-arrived_at",)
        indexes = [models.Index(fields=("identity_number", "arrived_at"), name="institution_visito_3a6ddc_idx")]

    def clean(self):
        errors = {}
        if self.visitation_window_id and self.student_id:
            if self.visitation_window.campus_id != self.student.campus_id:
                errors["visitation_window"] = "The visitation window belongs to another campus."
        if self.departed_at and self.departed_at < self.arrived_at:
            errors["departed_at"] = "Departure cannot be before arrival."
        if self.student_returned_at and not self.collected_student:
            errors["student_returned_at"] = "A return time requires a student collection record."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.visitor_name} visiting {self.student}"


class MealService(models.Model):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    SUPPER = "SUPPER"
    SNACK = "SNACK"
    OTHER = "OTHER"
    MEAL_CHOICES = ((BREAKFAST, "Breakfast"), (LUNCH, "Lunch"), (SUPPER, "Supper"), (SNACK, "Snack"), (OTHER, "Other"))

    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.CASCADE, related_name="meal_services")
    service_date = models.DateField(default=timezone.localdate)
    meal = models.CharField(max_length=16, choices=MEAL_CHOICES)
    served_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ("-service_date", "meal")
        constraints = [models.UniqueConstraint(fields=("campus", "service_date", "meal"), name="uniq_campus_daily_meal")]

    def __str__(self):
        return f"{self.campus} — {self.service_date} {self.get_meal_display()}"


class MealAttendance(models.Model):
    PRESENT = "PRESENT"
    MISSED = "MISSED"
    EXCUSED = "EXCUSED"
    SICK = "SICK"
    STATUS_CHOICES = ((PRESENT, "Present"), (MISSED, "Missed"), (EXCUSED, "Excused"), (SICK, "Sick"))

    service = models.ForeignKey(MealService, on_delete=models.CASCADE, related_name="attendance")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="meal_attendance")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PRESENT)
    note = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")
        constraints = [models.UniqueConstraint(fields=("service", "student"), name="uniq_meal_student")]

    def clean(self):
        if self.service_id and self.student_id and self.service.campus_id != self.student.campus_id:
            raise ValidationError({"student": "The learner belongs to another campus."})


class StudentProperty(models.Model):
    IN_CUSTODY = "IN_CUSTODY"
    RELEASED = "RELEASED"
    LOST = "LOST"
    DAMAGED = "DAMAGED"
    STATUS_CHOICES = ((IN_CUSTODY, "In custody"), (RELEASED, "Released"), (LOST, "Lost"), (DAMAGED, "Damaged"))

    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="property_records")
    item_name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    serial_number = models.CharField(max_length=128, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=IN_CUSTODY)
    received_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="property_received")
    released_to = models.CharField(max_length=160, blank=True)
    release_identity = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-received_at",)

    def clean(self):
        if self.status == self.RELEASED and not self.released_at:
            raise ValidationError({"released_at": "Record the release time for released property."})

    def __str__(self):
        return f"{self.student} — {self.item_name}"
