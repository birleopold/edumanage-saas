from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class LearningActivityProfile(models.Model):
    RESOURCE = "RESOURCE"
    ASSIGNMENT = "ASSIGNMENT"
    PROJECT = "PROJECT"
    PRACTICAL = "PRACTICAL"
    DISCUSSION = "DISCUSSION"
    LIVE_CLASS = "LIVE_CLASS"
    VIDEO = "VIDEO"
    QUIZ = "QUIZ"
    CLASSWORK = "CLASSWORK"
    WEEKEND_ASSIGNMENT = "WEEKEND_ASSIGNMENT"
    ESSAY = "ESSAY"
    LAB_REPORT = "LAB_REPORT"
    FIELDWORK = "FIELDWORK"
    GROUP_ASSIGNMENT = "GROUP_ASSIGNMENT"
    READING_EXERCISE = "READING_EXERCISE"
    RESEARCH_WORK = "RESEARCH_WORK"
    ACTIVITY_OF_INTEGRATION = "ACTIVITY_OF_INTEGRATION"
    OTHER = "OTHER"

    DETAILED_KIND_CHOICES = (
        (RESOURCE, "Learning resource"),
        (ASSIGNMENT, "Individual assignment"),
        (PROJECT, "Project"),
        (PRACTICAL, "Practical activity"),
        (DISCUSSION, "Discussion or debate"),
        (LIVE_CLASS, "Live class"),
        (VIDEO, "Video lesson"),
        (QUIZ, "Quiz or short task"),
        (CLASSWORK, "Classwork"),
        (WEEKEND_ASSIGNMENT, "Weekend assignment"),
        (ESSAY, "Essay"),
        (LAB_REPORT, "Laboratory report"),
        (FIELDWORK, "Fieldwork"),
        (GROUP_ASSIGNMENT, "Group assignment"),
        (READING_EXERCISE, "Reading exercise"),
        (RESEARCH_WORK, "Research work"),
        (ACTIVITY_OF_INTEGRATION, "Activity of Integration"),
        (OTHER, "Other learning activity"),
    )

    activity = models.OneToOneField(
        "coursework.LearningActivity",
        on_delete=models.CASCADE,
        related_name="workflow_profile",
    )
    detailed_kind = models.CharField(
        max_length=32,
        choices=DETAILED_KIND_CHOICES,
        default=OTHER,
    )
    group_work = models.BooleanField(default=False)
    resubmission_allowed = models.BooleanField(default=False)
    maximum_attempts = models.PositiveSmallIntegerField(default=1)
    late_grace_minutes = models.PositiveIntegerField(default=0)
    competency_tracking = models.BooleanField(default=False)
    competency_framework_key = models.CharField(max_length=96, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("activity__position", "activity__title_snapshot")

    def __str__(self):
        return f"{self.get_detailed_kind_display()} — {self.activity}"

    def clean(self):
        super().clean()
        errors = {}
        if self.maximum_attempts < 1:
            errors["maximum_attempts"] = "Maximum attempts must be at least one."
        if self.resubmission_allowed and self.maximum_attempts < 2:
            errors["maximum_attempts"] = (
                "Allow at least two attempts when resubmission is enabled."
            )
        if self.detailed_kind == self.GROUP_ASSIGNMENT and not self.group_work:
            errors["group_work"] = "Group assignments must enable group work."
        if self.group_work and not self.activity.assignment_id:
            errors["group_work"] = "Group work requires an assignment source."
        if self.competency_tracking and not self.competency_framework_key.strip():
            errors["competency_framework_key"] = (
                "Enter a competency framework or rubric key when competency tracking is enabled."
            )
        if errors:
            raise ValidationError(errors)


class AssignmentGroup(models.Model):
    activity = models.ForeignKey(
        "coursework.LearningActivity",
        on_delete=models.CASCADE,
        related_name="assignment_groups",
    )
    name = models.CharField(max_length=128)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coursework_groups_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("activity__title_snapshot", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("activity", "name"),
                name="uniq_coursework_activity_group",
            )
        ]

    def __str__(self):
        return f"{self.activity} — {self.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.activity_id and not self.activity.assignment_id:
            errors["activity"] = "Choose an activity backed by an assignment."
        if self.activity_id:
            profile = getattr(self.activity, "workflow_profile", None)
            if profile and not profile.group_work:
                errors["activity"] = "The selected activity is not configured for group work."
        if self.capacity is not None and self.capacity < 1:
            errors["capacity"] = "Capacity must be at least one."
        if errors:
            raise ValidationError(errors)


class AssignmentGroupMember(models.Model):
    MEMBER = "MEMBER"
    LEADER = "LEADER"
    SECRETARY = "SECRETARY"
    PRESENTER = "PRESENTER"
    OTHER = "OTHER"
    ROLE_CHOICES = (
        (MEMBER, "Member"),
        (LEADER, "Group leader"),
        (SECRETARY, "Secretary"),
        (PRESENTER, "Presenter"),
        (OTHER, "Other"),
    )

    group = models.ForeignKey(
        AssignmentGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="coursework_group_memberships",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=MEMBER)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("group", "student__last_name", "student__first_name")
        constraints = [
            models.UniqueConstraint(
                fields=("group", "student"),
                name="uniq_coursework_group_student",
            )
        ]

    def __str__(self):
        return f"{self.group} — {self.student}"

    def clean(self):
        super().clean()
        errors = {}
        if self.group_id and self.student_id:
            activity = self.group.activity
            campus = activity.campus
            if campus and self.student.campus_id != campus.pk:
                errors["student"] = "The learner belongs to another campus."
            if self.is_active and self.group.capacity:
                existing = type(self).objects.filter(
                    group=self.group,
                    is_active=True,
                )
                if self.pk:
                    existing = existing.exclude(pk=self.pk)
                if existing.count() >= self.group.capacity:
                    errors["student"] = "This assignment group has reached capacity."
        if errors:
            raise ValidationError(errors)


class SubmissionWorkflow(models.Model):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    LATE = "LATE"
    EXCUSED_LATE = "EXCUSED_LATE"
    RETURNED = "RETURNED"
    RESUBMISSION_REQUIRED = "RESUBMISSION_REQUIRED"
    RESUBMITTED = "RESUBMITTED"
    MARKED = "MARKED"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted"),
        (LATE, "Submitted late"),
        (EXCUSED_LATE, "Late submission excused"),
        (RETURNED, "Returned to learner"),
        (RESUBMISSION_REQUIRED, "Resubmission required"),
        (RESUBMITTED, "Resubmitted"),
        (MARKED, "Marked"),
    )

    ACHIEVED = "ACHIEVED"
    DEVELOPING = "DEVELOPING"
    NEEDS_SUPPORT = "NEEDS_SUPPORT"
    NOT_ASSESSED = "NOT_ASSESSED"
    COMPETENCY_CHOICES = (
        (ACHIEVED, "Achieved"),
        (DEVELOPING, "Developing"),
        (NEEDS_SUPPORT, "Needs support"),
        (NOT_ASSESSED, "Not assessed"),
    )

    submission = models.OneToOneField(
        "coursework.AssignmentSubmission",
        on_delete=models.CASCADE,
        related_name="workflow",
    )
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=DRAFT)
    is_late = models.BooleanField(default=False)
    late_excused = models.BooleanField(default=False)
    late_reason = models.TextField(blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=1)
    first_submitted_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    resubmitted_at = models.DateTimeField(null=True, blank=True)
    competency_rating = models.CharField(
        max_length=24,
        choices=COMPETENCY_CHOICES,
        default=NOT_ASSESSED,
    )
    competency_evidence = models.TextField(blank=True)
    settings = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"{self.submission} — {self.get_status_display()}"

    @property
    def activity_profile(self):
        activity = self.submission.activity
        return getattr(activity, "workflow_profile", None) if activity else None

    def clean(self):
        super().clean()
        errors = {}
        profile = self.activity_profile
        if self.attempt_count < 1:
            errors["attempt_count"] = "Attempt count must be at least one."
        if profile and self.attempt_count > profile.maximum_attempts:
            errors["attempt_count"] = "The activity's maximum attempts have been exceeded."
        if self.status in {self.RESUBMISSION_REQUIRED, self.RESUBMITTED}:
            if profile and not profile.resubmission_allowed:
                errors["status"] = "This activity does not allow resubmission."
        if self.late_excused and not self.is_late:
            errors["late_excused"] = "Only a late submission can be excused."
        if self.status == self.EXCUSED_LATE and not self.late_excused:
            errors["late_excused"] = "Mark the late submission as excused."
        if profile and profile.competency_tracking:
            if self.status == self.MARKED and self.competency_rating == self.NOT_ASSESSED:
                errors["competency_rating"] = (
                    "Record a competency rating before marking this activity complete."
                )
        if errors:
            raise ValidationError(errors)


class GroupSubmission(models.Model):
    activity = models.ForeignKey(
        "coursework.LearningActivity",
        on_delete=models.CASCADE,
        related_name="group_submissions",
    )
    group = models.ForeignKey(
        AssignmentGroup,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    text_answer = models.TextField(blank=True)
    status = models.CharField(
        max_length=24,
        choices=SubmissionWorkflow.STATUS_CHOICES,
        default=SubmissionWorkflow.DRAFT,
    )
    attempt_count = models.PositiveSmallIntegerField(default=1)
    first_submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_late = models.BooleanField(default=False)
    late_excused = models.BooleanField(default=False)
    late_reason = models.TextField(blank=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    competency_rating = models.CharField(
        max_length=24,
        choices=SubmissionWorkflow.COMPETENCY_CHOICES,
        default=SubmissionWorkflow.NOT_ASSESSED,
    )
    competency_evidence = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coursework_group_submissions_made",
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_group_submissions",
    )
    marked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("activity", "group"),
                name="uniq_coursework_activity_group_submission",
            )
        ]

    def __str__(self):
        return f"{self.activity} — {self.group}"

    def clean(self):
        super().clean()
        errors = {}
        if self.group_id and self.activity_id and self.group.activity_id != self.activity_id:
            errors["group"] = "The group must belong to this learning activity."
        profile = getattr(self.activity, "workflow_profile", None) if self.activity_id else None
        if profile and not profile.group_work:
            errors["activity"] = "The activity is not configured for group work."
        if self.submitted_by_id and self.group_id:
            if not self.group.memberships.filter(
                student_id=self.submitted_by_id,
                is_active=True,
            ).exists():
                errors["submitted_by"] = "The submitting learner is not an active group member."
        if profile and self.attempt_count > profile.maximum_attempts:
            errors["attempt_count"] = "The activity's maximum attempts have been exceeded."
        if self.late_excused and not self.is_late:
            errors["late_excused"] = "Only a late submission can be excused."
        if profile and profile.competency_tracking:
            if self.status == SubmissionWorkflow.MARKED and self.competency_rating == SubmissionWorkflow.NOT_ASSESSED:
                errors["competency_rating"] = (
                    "Record a competency rating before marking this group work complete."
                )
        if errors:
            raise ValidationError(errors)


class GroupSubmissionAttachment(models.Model):
    submission = models.ForeignKey(
        GroupSubmission,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="coursework/group-submissions/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self):
        return f"{self.submission}: {self.file.name}"
