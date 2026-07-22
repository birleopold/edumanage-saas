from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SchoolHouse(models.Model):
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.CASCADE,
        related_name="school_houses",
    )
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    motto = models.CharField(max_length=180, blank=True)
    identity_label = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional colour, symbol, saint, founder, or local identity label.",
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("campus__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("campus", "code"),
                name="uniq_campus_school_house_code",
            ),
            models.UniqueConstraint(
                fields=("campus", "name"),
                name="uniq_campus_school_house_name",
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        super().clean()
        if self.capacity is not None and self.capacity < 1:
            raise ValidationError({"capacity": "House capacity must be at least one."})


class HouseMembership(models.Model):
    house = models.ForeignKey(
        SchoolHouse,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="house_memberships",
    )
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="house_memberships_assigned",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("house__name", "student__last_name", "student__first_name")
        constraints = [
            models.UniqueConstraint(
                fields=("student",),
                condition=models.Q(is_active=True),
                name="uniq_active_house_membership_student",
            )
        ]

    def __str__(self):
        return f"{self.student} — {self.house}"

    def clean(self):
        super().clean()
        errors = {}
        if self.student_id and self.house_id:
            if self.student.campus_id != self.house.campus_id:
                errors["student"] = "The learner and school house must belong to the same campus."
            if self.is_active and self.house.capacity:
                active = type(self).objects.filter(
                    house=self.house,
                    is_active=True,
                )
                if self.pk:
                    active = active.exclude(pk=self.pk)
                if active.count() >= self.house.capacity:
                    errors["house"] = "The school house has reached its configured capacity."
        if self.ends_on and self.ends_on < self.starts_on:
            errors["ends_on"] = "Membership end date cannot be before its start date."
        if self.ends_on and self.is_active:
            errors["is_active"] = "A membership with an end date cannot remain active."
        if errors:
            raise ValidationError(errors)


class HouseStaffAssignment(models.Model):
    HOUSE_MASTER = "HOUSE_MASTER"
    HOUSE_MISTRESS = "HOUSE_MISTRESS"
    MATRON = "MATRON"
    WARDEN = "WARDEN"
    DEPUTY = "DEPUTY"
    PATRON = "PATRON"
    RESIDENT_TUTOR = "RESIDENT_TUTOR"
    OTHER = "OTHER"
    ROLE_CHOICES = (
        (HOUSE_MASTER, "House master"),
        (HOUSE_MISTRESS, "House mistress"),
        (MATRON, "Matron"),
        (WARDEN, "Warden"),
        (DEPUTY, "Deputy house staff"),
        (PATRON, "House patron"),
        (RESIDENT_TUTOR, "Resident tutor"),
        (OTHER, "Other house responsibility"),
    )

    house = models.ForeignKey(
        SchoolHouse,
        on_delete=models.CASCADE,
        related_name="staff_assignments",
    )
    staff = models.ForeignKey(
        "hr.StaffProfile",
        on_delete=models.PROTECT,
        related_name="house_assignments",
    )
    role = models.CharField(max_length=24, choices=ROLE_CHOICES)
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_resident = models.BooleanField(default=False)
    duty_phone = models.CharField(max_length=32, blank=True)
    responsibilities = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="house_staff_assignments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("house__name", "role", "staff__last_name")
        constraints = [
            models.UniqueConstraint(
                fields=("house", "staff", "role"),
                condition=models.Q(is_active=True),
                name="uniq_active_house_staff_role",
            )
        ]

    def __str__(self):
        return f"{self.house} — {self.get_role_display()} — {self.staff}"

    def clean(self):
        super().clean()
        errors = {}
        if self.staff_id and self.house_id:
            staff_campus_id = getattr(self.staff, "campus_id", None)
            if staff_campus_id and staff_campus_id != self.house.campus_id:
                errors["staff"] = "The staff member belongs to another campus."
        if self.ends_on and self.ends_on < self.starts_on:
            errors["ends_on"] = "Assignment end date cannot be before its start date."
        if self.ends_on and self.is_active:
            errors["is_active"] = "An assignment with an end date cannot remain active."
        if self.is_primary and self.is_active:
            duplicate = type(self).objects.filter(
                house=self.house,
                role=self.role,
                is_primary=True,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                errors["is_primary"] = "This house already has a primary staff member for the selected role."
        if errors:
            raise ValidationError(errors)


class BoardingDutyRoster(models.Model):
    MORNING = "MORNING"
    DAY = "DAY"
    EVENING = "EVENING"
    NIGHT = "NIGHT"
    WEEKEND = "WEEKEND"
    CUSTOM = "CUSTOM"
    SHIFT_CHOICES = (
        (MORNING, "Morning duty"),
        (DAY, "Day duty"),
        (EVENING, "Evening duty"),
        (NIGHT, "Night duty"),
        (WEEKEND, "Weekend duty"),
        (CUSTOM, "Custom duty"),
    )

    SCHEDULED = "SCHEDULED"
    ON_DUTY = "ON_DUTY"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = (
        (SCHEDULED, "Scheduled"),
        (ON_DUTY, "On duty"),
        (COMPLETED, "Completed"),
        (MISSED, "Missed"),
        (CANCELLED, "Cancelled"),
    )

    assignment = models.ForeignKey(
        HouseStaffAssignment,
        on_delete=models.PROTECT,
        related_name="duty_rosters",
    )
    shift = models.CharField(max_length=16, choices=SHIFT_CHOICES, default=EVENING)
    duty_starts_at = models.DateTimeField()
    duty_ends_at = models.DateTimeField()
    duty_area = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=SCHEDULED)
    instructions = models.TextField(blank=True)
    incidents_summary = models.TextField(blank=True)
    handover_note = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boarding_duties_completed",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boarding_duties_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-duty_starts_at", "assignment__house__name")
        indexes = [
            models.Index(fields=("status", "duty_starts_at", "duty_ends_at")),
        ]

    def __str__(self):
        return f"{self.assignment} — {self.duty_starts_at:%d %b %Y %H:%M}"

    def clean(self):
        super().clean()
        errors = {}
        if self.duty_ends_at <= self.duty_starts_at:
            errors["duty_ends_at"] = "Duty must end after it starts."
        if self.assignment_id and not self.assignment.is_active:
            errors["assignment"] = "Choose an active house staff assignment."
        if self.status == self.COMPLETED:
            if not self.completed_at:
                errors["completed_at"] = "Record the completion time."
            if not self.handover_note.strip():
                errors["handover_note"] = "Record a handover note for completed duty."
        if errors:
            raise ValidationError(errors)
