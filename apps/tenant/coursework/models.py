import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import Q
from django.utils import timezone


def coursework_upload_to(instance, filename: str) -> str:
    schema = getattr(connection, "schema_name", "public") or "public"
    return f"{schema}/coursework/{filename}"


class LearningMaterial(models.Model):
    HOMEWORK = "HOMEWORK"
    NOTES = "NOTES"
    HOLIDAY_PACKAGE = "HOLIDAY_PACKAGE"
    VIDEO_LESSON = "VIDEO_LESSON"
    LIVE_CLASS = "LIVE_CLASS"

    TYPE_CHOICES = (
        (HOMEWORK, "Homework"),
        (NOTES, "Class Notes"),
        (HOLIDAY_PACKAGE, "Holiday Package"),
        (VIDEO_LESSON, "Video Lesson"),
        (LIVE_CLASS, "Live Class"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    class_group = models.ForeignKey("academics.ClassGroup", on_delete=models.SET_NULL, null=True, blank=True)
    stream = models.ForeignKey("academics.Stream", on_delete=models.SET_NULL, null=True, blank=True)
    offering = models.ForeignKey(
        "academics.CourseOffering",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_materials",
    )

    external_url = models.URLField(blank=True, help_text="Optional website, YouTube, Google Drive, or other learning link.")
    video_url = models.URLField(blank=True, help_text="Optional video lesson link.")
    meeting_url = models.URLField(blank=True, help_text="Optional Google Meet, Zoom, or live class link.")
    allow_comments = models.BooleanField(default=True)

    publish_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_learning_materials",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-publish_at", "-created_at")

    def __str__(self) -> str:
        return self.title


class LearningMaterialAttachment(models.Model):
    material = models.ForeignKey(LearningMaterial, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=coursework_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return f"{self.material}: {self.file.name}"


class Assignment(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    class_group = models.ForeignKey("academics.ClassGroup", on_delete=models.SET_NULL, null=True, blank=True)
    stream = models.ForeignKey("academics.Stream", on_delete=models.SET_NULL, null=True, blank=True)
    offering = models.ForeignKey(
        "academics.CourseOffering",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )

    resource_url = models.URLField(blank=True, help_text="Optional instruction, reference, video, or live class link.")
    allow_comments = models.BooleanField(default=True)

    publish_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-publish_at", "-created_at")

    def __str__(self) -> str:
        return self.title


class LearningActivity(models.Model):
    RESOURCE = "RESOURCE"
    ASSIGNMENT = "ASSIGNMENT"
    PROJECT = "PROJECT"
    PRACTICAL = "PRACTICAL"
    DISCUSSION = "DISCUSSION"
    LIVE_CLASS = "LIVE_CLASS"
    VIDEO = "VIDEO"
    QUIZ = "QUIZ"
    OTHER = "OTHER"

    KIND_CHOICES = (
        (RESOURCE, "Learning resource"),
        (ASSIGNMENT, "Assignment"),
        (PROJECT, "Project"),
        (PRACTICAL, "Practical activity"),
        (DISCUSSION, "Discussion"),
        (LIVE_CLASS, "Live class"),
        (VIDEO, "Video lesson"),
        (QUIZ, "Quiz or short task"),
        (OTHER, "Other learning activity"),
    )

    COMPLETION_NONE = "NONE"
    COMPLETION_VIEW = "VIEW"
    COMPLETION_MANUAL = "MANUAL"
    COMPLETION_SUBMISSION = "SUBMISSION"
    COMPLETION_SCORE = "SCORE"
    COMPLETION_CHOICES = (
        (COMPLETION_NONE, "No completion tracking"),
        (COMPLETION_VIEW, "Complete after viewing"),
        (COMPLETION_MANUAL, "Learner marks complete"),
        (COMPLETION_SUBMISSION, "Complete after submission"),
        (COMPLETION_SCORE, "Complete after marking"),
    )

    SUBMISSION_NONE = "NONE"
    SUBMISSION_OPTIONAL = "OPTIONAL"
    SUBMISSION_REQUIRED = "REQUIRED"
    SUBMISSION_CHOICES = (
        (SUBMISSION_NONE, "No submission"),
        (SUBMISSION_OPTIONAL, "Optional submission"),
        (SUBMISSION_REQUIRED, "Required submission"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    material = models.OneToOneField(
        LearningMaterial,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="unified_activity",
    )
    assignment = models.OneToOneField(
        Assignment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="unified_activity",
    )
    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default=OTHER)
    title_snapshot = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=0)
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)
    completion_policy = models.CharField(max_length=16, choices=COMPLETION_CHOICES, default=COMPLETION_MANUAL)
    submission_policy = models.CharField(max_length=16, choices=SUBMISSION_CHOICES, default=SUBMISSION_NONE)
    assessment_type = models.ForeignKey(
        "assessments.AssessmentType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_activities",
    )
    weighting_component = models.ForeignKey(
        "assessments.AssessmentWeightingComponent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_activities",
    )
    local_aliases = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(material__isnull=False, assignment__isnull=True)
                    | Q(material__isnull=True, assignment__isnull=False)
                ),
                name="coursework_activity_exactly_one_source",
            ),
        ]
        indexes = [
            models.Index(fields=["kind", "is_active"]),
            models.Index(fields=["position", "created_at"]),
        ]

    def clean(self):
        errors = {}
        if bool(self.material_id) == bool(self.assignment_id):
            errors["material"] = "Select exactly one source: a learning material or an assignment."
            errors["assignment"] = "Select exactly one source: a learning material or an assignment."
        if (
            self.assessment_type_id
            and self.weighting_component_id
            and self.weighting_component.assessment_type_id != self.assessment_type_id
        ):
            errors["weighting_component"] = "The weighting component must use the selected assessment type."
        if self.estimated_minutes is not None and self.estimated_minutes < 1:
            errors["estimated_minutes"] = "Estimated duration must be at least one minute."
        if errors:
            raise ValidationError(errors)

    @property
    def source(self):
        return self.material or self.assignment

    @property
    def source_type(self) -> str:
        return "material" if self.material_id else "assignment"

    @property
    def title(self) -> str:
        source = self.source
        return getattr(source, "title", self.title_snapshot)

    @property
    def description(self) -> str:
        source = self.source
        if self.material_id:
            return getattr(source, "description", "")
        return getattr(source, "instructions", "")

    @property
    def campus(self):
        return getattr(self.source, "campus", None)

    @property
    def class_group(self):
        return getattr(self.source, "class_group", None)

    @property
    def stream(self):
        return getattr(self.source, "stream", None)

    @property
    def offering(self):
        return getattr(self.source, "offering", None)

    @property
    def publish_at(self):
        return getattr(self.source, "publish_at", None)

    @property
    def due_at(self):
        return getattr(self.source, "due_date", None)

    @property
    def allow_comments(self) -> bool:
        return bool(getattr(self.source, "allow_comments", False))

    def display_name(self, country_code: str = "") -> str:
        aliases = self.local_aliases or {}
        return aliases.get((country_code or "").upper()) or aliases.get("default") or self.get_kind_display()

    def __str__(self) -> str:
        return self.title


class AssignmentAttachment(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=coursework_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return f"{self.assignment}: {self.file.name}"


class AssignmentSubmission(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    activity = models.ForeignKey(
        LearningActivity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="assignment_submissions")

    text_answer = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_assignment_submissions",
    )
    marked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("assignment", "student")
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return f"{self.assignment} -> {self.student}"


class AssignmentSubmissionAttachment(models.Model):
    submission = models.ForeignKey(AssignmentSubmission, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=coursework_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return f"{self.submission}: {self.file.name}"


class CourseworkComment(models.Model):
    material = models.ForeignKey(LearningMaterial, on_delete=models.CASCADE, null=True, blank=True, related_name="comments")
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True, related_name="comments")
    activity = models.ForeignKey(
        LearningActivity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comments",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    body = models.TextField()
    is_teacher_reply = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        target = self.material or self.assignment
        return f"Comment on {target}"


class CourseworkProgress(models.Model):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="coursework_progress")
    material = models.ForeignKey(LearningMaterial, on_delete=models.CASCADE, null=True, blank=True, related_name="progress_records")
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True, related_name="progress_records")
    activity = models.ForeignKey(
        LearningActivity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_records",
    )
    viewed_at = models.DateTimeField(null=True, blank=True)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    percent_complete = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["student", "material"]),
            models.Index(fields=["student", "assignment"]),
            models.Index(fields=["student", "activity"]),
        ]

    def __str__(self) -> str:
        target = self.material or self.assignment
        return f"{self.student} progress: {target}"
