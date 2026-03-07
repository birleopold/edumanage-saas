import uuid

from django.conf import settings
from django.db import connection, models
from django.utils import timezone


def coursework_upload_to(instance, filename: str) -> str:
    schema = getattr(connection, "schema_name", "public") or "public"
    return f"{schema}/coursework/{filename}"


class LearningMaterial(models.Model):
    HOMEWORK = "HOMEWORK"
    NOTES = "NOTES"
    HOLIDAY_PACKAGE = "HOLIDAY_PACKAGE"

    TYPE_CHOICES = (
        (HOMEWORK, "Homework"),
        (NOTES, "Class Notes"),
        (HOLIDAY_PACKAGE, "Holiday Package"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    class_group = models.ForeignKey(
        "academics.ClassGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    stream = models.ForeignKey(
        "academics.Stream",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    offering = models.ForeignKey(
        "academics.CourseOffering",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_materials",
    )

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

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    class_group = models.ForeignKey(
        "academics.ClassGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    stream = models.ForeignKey(
        "academics.Stream",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    offering = models.ForeignKey(
        "academics.CourseOffering",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )

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
