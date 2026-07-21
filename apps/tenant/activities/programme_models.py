from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .models import Activity, ActivityMember


class ActivityProgramme(models.Model):
    OPEN = "OPEN"
    SELECTIVE = "SELECTIVE"
    TEAM = "TEAM"
    PARTICIPATION_CHOICES = (
        (OPEN, "Open participation"),
        (SELECTIVE, "Selective participation"),
        (TEAM, "Team or squad based"),
    )

    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        related_name="programme_profile",
    )
    code = models.CharField(max_length=64, unique=True)
    participation_mode = models.CharField(
        max_length=16,
        choices=PARTICIPATION_CHOICES,
        default=OPEN,
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    attendance_required = models.BooleanField(default=True)
    guardian_consent_required = models.BooleanField(default=False)
    medical_clearance_required = models.BooleanField(default=False)
    competitive = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("activity__name",)

    def __str__(self):
        return f"{self.code} - {self.activity}"


class ActivityGroup(models.Model):
    TEAM = "TEAM"
    SQUAD = "SQUAD"
    ENSEMBLE = "ENSEMBLE"
    COMMITTEE = "COMMITTEE"
    HOUSE = "HOUSE"
    OTHER = "OTHER"
    GROUP_TYPE_CHOICES = (
        (TEAM, "Team"),
        (SQUAD, "Squad"),
        (ENSEMBLE, "Ensemble"),
        (COMMITTEE, "Committee"),
        (HOUSE, "House"),
        (OTHER, "Other"),
    )

    programme = models.ForeignKey(
        ActivityProgramme,
        on_delete=models.CASCADE,
        related_name="groups",
    )
    name = models.CharField(max_length=128)
    group_type = models.CharField(max_length=16, choices=GROUP_TYPE_CHOICES, default=TEAM)
    coach = models.ForeignKey(
        "hr.StaffProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_groups_coached",
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("programme__activity__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["programme", "name"],
                name="uniq_activity_programme_group",
            )
        ]

    def __str__(self):
        return f"{self.programme.activity} - {self.name}"


class ActivityParticipation(models.Model):
    MEMBER = "MEMBER"
    CAPTAIN = "CAPTAIN"
    LEADER = "LEADER"
    SECRETARY = "SECRETARY"
    TREASURER = "TREASURER"
    PREFECT = "PREFECT"
    OTHER = "OTHER"
    ROLE_CHOICES = (
        (MEMBER, "Member"),
        (CAPTAIN, "Captain"),
        (LEADER, "Leader"),
        (SECRETARY, "Secretary"),
        (TREASURER, "Treasurer"),
        (PREFECT, "Prefect"),
        (OTHER, "Other"),
    )

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CLEARANCE_CHOICES = (
        (NOT_REQUIRED, "Not required"),
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (DECLINED, "Declined"),
        (EXPIRED, "Expired"),
    )

    membership = models.OneToOneField(
        ActivityMember,
        on_delete=models.CASCADE,
        related_name="participation_profile",
    )
    group = models.ForeignKey(
        ActivityGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participants",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=MEMBER)
    guardian_consent_status = models.CharField(
        max_length=20,
        choices=CLEARANCE_CHOICES,
        default=NOT_REQUIRED,
    )
    guardian_consent_recorded_at = models.DateTimeField(null=True, blank=True)
    medical_clearance_status = models.CharField(
        max_length=20,
        choices=CLEARANCE_CHOICES,
        default=NOT_REQUIRED,
    )
    medical_clearance_recorded_at = models.DateTimeField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)
    notes = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_participations_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("membership__activity__name", "membership__student__last_name")

    def __str__(self):
        return f"{self.membership} - {self.get_role_display()}"

    def clean(self):
        super().clean()
        if self.group_id and self.group.programme.activity_id != self.membership.activity_id:
            raise ValidationError({"group": "The selected group must belong to the membership activity."})


class ActivitySession(models.Model):
    MEETING = "MEETING"
    TRAINING = "TRAINING"
    PRACTICE = "PRACTICE"
    MATCH = "MATCH"
    COMPETITION = "COMPETITION"
    PERFORMANCE = "PERFORMANCE"
    SERVICE = "SERVICE"
    TRIP = "TRIP"
    OTHER = "OTHER"
    SESSION_TYPE_CHOICES = (
        (MEETING, "Meeting"),
        (TRAINING, "Training"),
        (PRACTICE, "Practice"),
        (MATCH, "Match"),
        (COMPETITION, "Competition"),
        (PERFORMANCE, "Performance"),
        (SERVICE, "Service activity"),
        (TRIP, "Trip"),
        (OTHER, "Other"),
    )

    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    LOCKED = "LOCKED"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
        (LOCKED, "Locked"),
    )

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="programme_sessions")
    group = models.ForeignKey(
        ActivityGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    title = models.CharField(max_length=200)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES, default=MEETING)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=180, blank=True)
    attendance_required = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_sessions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-starts_at", "activity__name")
        indexes = [models.Index(fields=["activity", "status", "starts_at"])]

    def __str__(self):
        return f"{self.activity} - {self.title}"

    def clean(self):
        super().clean()
        errors = {}
        if self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "End time must be after the start time."
        if self.group_id and self.group.programme.activity_id != self.activity_id:
            errors["group"] = "The selected group must belong to this activity."
        if errors:
            raise ValidationError(errors)


class ActivityAttendance(models.Model):
    UNMARKED = "UNMARKED"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"
    LATE = "LATE"
    INJURED = "INJURED"
    ON_DUTY = "ON_DUTY"
    STATUS_CHOICES = (
        (UNMARKED, "Not marked"),
        (PRESENT, "Present"),
        (ABSENT, "Absent"),
        (EXCUSED, "Excused"),
        (LATE, "Late"),
        (INJURED, "Injured or medically excused"),
        (ON_DUTY, "On school duty"),
    )

    session = models.ForeignKey(ActivitySession, on_delete=models.CASCADE, related_name="attendance_entries")
    membership = models.ForeignKey(
        ActivityMember,
        on_delete=models.CASCADE,
        related_name="session_attendance",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=UNMARKED)
    note = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_attendance_marked",
    )
    marked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("membership__student__last_name", "membership__student__first_name")
        constraints = [
            models.UniqueConstraint(
                fields=["session", "membership"],
                name="uniq_activity_session_membership",
            )
        ]

    def __str__(self):
        return f"{self.session} - {self.membership.student}"

    def clean(self):
        super().clean()
        if self.membership_id and self.session_id:
            if self.membership.activity_id != self.session.activity_id:
                raise ValidationError({"membership": "The membership must belong to the session activity."})

    def save(self, *args, **kwargs):
        if self.status != self.UNMARKED and not self.marked_at:
            self.marked_at = timezone.now()
        super().save(*args, **kwargs)


class ActivityAchievement(models.Model):
    PARTICIPATION = "PARTICIPATION"
    LEADERSHIP = "LEADERSHIP"
    AWARD = "AWARD"
    MEDAL = "MEDAL"
    CERTIFICATE = "CERTIFICATE"
    RECORD = "RECORD"
    SERVICE = "SERVICE"
    OTHER = "OTHER"
    TYPE_CHOICES = (
        (PARTICIPATION, "Participation"),
        (LEADERSHIP, "Leadership"),
        (AWARD, "Award"),
        (MEDAL, "Medal"),
        (CERTIFICATE, "Certificate"),
        (RECORD, "Record"),
        (SERVICE, "Service"),
        (OTHER, "Other"),
    )

    SCHOOL = "SCHOOL"
    DISTRICT = "DISTRICT"
    REGIONAL = "REGIONAL"
    NATIONAL = "NATIONAL"
    INTERNATIONAL = "INTERNATIONAL"
    OTHER_LEVEL = "OTHER"
    LEVEL_CHOICES = (
        (SCHOOL, "School"),
        (DISTRICT, "District"),
        (REGIONAL, "Regional"),
        (NATIONAL, "National"),
        (INTERNATIONAL, "International"),
        (OTHER_LEVEL, "Other"),
    )

    membership = models.ForeignKey(
        ActivityMember,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    session = models.ForeignKey(
        ActivitySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="achievements",
    )
    title = models.CharField(max_length=200)
    achievement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=PARTICIPATION)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=SCHOOL)
    achieved_on = models.DateField(default=timezone.localdate)
    position = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_achievements_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-achieved_on", "membership__activity__name")

    def __str__(self):
        return f"{self.membership.student} - {self.title}"

    def clean(self):
        super().clean()
        if self.session_id and self.session.activity_id != self.membership.activity_id:
            raise ValidationError({"session": "The session must belong to the membership activity."})
