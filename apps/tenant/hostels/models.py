from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Hostel(models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        unique_together = ("name", "code")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.code else self.name


class HostelRoom(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("hostel__name", "name")
        unique_together = ("hostel", "name", "code")

    def __str__(self) -> str:
        return f"{self.hostel} - {self.name}" if self.name else str(self.hostel)


class Bed(models.Model):
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, related_name="beds")
    label = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("room__hostel__name", "room__name", "label")
        unique_together = ("room", "label")

    def __str__(self) -> str:
        return f"{self.room} - {self.label}"


class BedAllocation(models.Model):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"

    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (ENDED, "Ended"),
    )

    bed = models.ForeignKey(Bed, on_delete=models.CASCADE)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["bed"],
                condition=models.Q(status="ACTIVE"),
                name="uniq_active_bed_allocation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student} -> {self.bed}"


class BoardingProfile(models.Model):
    DAY = "DAY"
    BOARDER = "BOARDER"
    WEEKLY = "WEEKLY"
    FLEXIBLE = "FLEXIBLE"

    BOARDING_STATUS_CHOICES = (
        (DAY, "Day learner"),
        (BOARDER, "Full boarder"),
        (WEEKLY, "Weekly boarder"),
        (FLEXIBLE, "Flexible boarding arrangement"),
    )

    student = models.OneToOneField(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="boarding_profile",
    )
    boarding_status = models.CharField(
        max_length=16,
        choices=BOARDING_STATUS_CHOICES,
        default=DAY,
    )
    primary_guardian_name = models.CharField(max_length=150, blank=True)
    primary_guardian_phone = models.CharField(max_length=32, blank=True)
    alternate_contact_name = models.CharField(max_length=150, blank=True)
    alternate_contact_phone = models.CharField(max_length=32, blank=True)
    authorised_pickup_people = models.JSONField(default=list, blank=True)
    dietary_requirements = models.TextField(blank=True)
    accessibility_support = models.TextField(blank=True)
    safeguarding_note = models.TextField(
        blank=True,
        help_text="Sensitive boarding or safeguarding information. Limit access to authorised staff.",
    )
    general_note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")

    def __str__(self) -> str:
        return f"Boarding profile - {self.student}"

    @property
    def current_allocation(self):
        return (
            BedAllocation.objects.filter(student=self.student, status=BedAllocation.ACTIVE)
            .select_related("bed", "bed__room", "bed__room__hostel")
            .first()
        )

    @property
    def is_boarder(self) -> bool:
        return self.boarding_status in {self.BOARDER, self.WEEKLY, self.FLEXIBLE}


class BoardingLeave(models.Model):
    HOME = "HOME"
    MEDICAL = "MEDICAL"
    ACTIVITY = "ACTIVITY"
    EMERGENCY = "EMERGENCY"
    OTHER = "OTHER"

    LEAVE_TYPE_CHOICES = (
        (HOME, "Home leave"),
        (MEDICAL, "Medical leave"),
        (ACTIVITY, "School activity"),
        (EMERGENCY, "Emergency leave"),
        (OTHER, "Other"),
    )

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DEPARTED = "DEPARTED"
    RETURNED = "RETURNED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = (
        (PENDING, "Pending approval"),
        (APPROVED, "Approved"),
        (DEPARTED, "Departed"),
        (RETURNED, "Returned"),
        (REJECTED, "Rejected"),
        (CANCELLED, "Cancelled"),
    )

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="boarding_leaves",
    )
    bed_allocation = models.ForeignKey(
        BedAllocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boarding_leaves",
    )
    linked_sickbay_visit = models.ForeignKey(
        "sickbay.SickbayVisit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boarding_leaves",
    )
    leave_type = models.CharField(max_length=16, choices=LEAVE_TYPE_CHOICES, default=HOME)
    expected_departure_at = models.DateTimeField()
    expected_return_at = models.DateTimeField()
    destination = models.CharField(max_length=200, blank=True)
    reason = models.TextField(blank=True)
    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_phone = models.CharField(max_length=32, blank=True)
    handover_to = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boarding_leaves_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    departed_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boarding_leaves_recorded",
    )
    return_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-expected_departure_at", "-created_at")
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["status", "expected_return_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.get_leave_type_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.expected_return_at and self.expected_departure_at:
            if self.expected_return_at <= self.expected_departure_at:
                errors["expected_return_at"] = "Expected return must be after departure."
        if self.bed_allocation_id and self.student_id:
            if self.bed_allocation.student_id != self.student_id:
                errors["bed_allocation"] = "The bed allocation must belong to the selected student."
        if self.linked_sickbay_visit_id and self.student_id:
            if self.linked_sickbay_visit.student_id != self.student_id:
                errors["linked_sickbay_visit"] = "The sickbay visit must belong to the selected student."
        if errors:
            raise ValidationError(errors)

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.status == self.DEPARTED
            and self.expected_return_at
            and self.expected_return_at < timezone.now()
        )


class HostelRollCall(models.Model):
    MORNING = "MORNING"
    EVENING = "EVENING"
    NIGHT = "NIGHT"
    CUSTOM = "CUSTOM"

    SHIFT_CHOICES = (
        (MORNING, "Morning"),
        (EVENING, "Evening"),
        (NIGHT, "Night"),
        (CUSTOM, "Custom"),
    )

    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"
    LOCKED = "LOCKED"

    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (COMPLETED, "Completed"),
        (LOCKED, "Locked"),
    )

    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="roll_calls")
    roll_call_date = models.DateField(default=timezone.localdate)
    shift = models.CharField(max_length=16, choices=SHIFT_CHOICES, default=EVENING)
    taken_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hostel_roll_calls_recorded",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-roll_call_date", "hostel__name", "shift")
        constraints = [
            models.UniqueConstraint(
                fields=["hostel", "roll_call_date", "shift"],
                name="uniq_hostel_roll_call_shift",
            )
        ]

    def __str__(self) -> str:
        return f"{self.hostel} - {self.roll_call_date} ({self.get_shift_display()})"


class HostelRollCallEntry(models.Model):
    UNMARKED = "UNMARKED"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"
    SICK = "SICK"
    ON_LEAVE = "ON_LEAVE"

    PRESENCE_CHOICES = (
        (UNMARKED, "Not marked"),
        (PRESENT, "Present"),
        (ABSENT, "Absent"),
        (EXCUSED, "Excused"),
        (SICK, "Sick"),
        (ON_LEAVE, "On approved leave"),
    )

    roll_call = models.ForeignKey(HostelRollCall, on_delete=models.CASCADE, related_name="entries")
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="hostel_roll_call_entries",
    )
    bed_allocation = models.ForeignKey(
        BedAllocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roll_call_entries",
    )
    boarding_leave = models.ForeignKey(
        BoardingLeave,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roll_call_entries",
    )
    presence = models.CharField(max_length=16, choices=PRESENCE_CHOICES, default=UNMARKED)
    note = models.CharField(max_length=255, blank=True)
    checked_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")
        constraints = [
            models.UniqueConstraint(
                fields=["roll_call", "student"],
                name="uniq_roll_call_student",
            )
        ]

    def __str__(self) -> str:
        return f"{self.roll_call}: {self.student} - {self.get_presence_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.bed_allocation_id and self.bed_allocation.student_id != self.student_id:
            errors["bed_allocation"] = "The allocation must belong to the selected student."
        if self.boarding_leave_id and self.boarding_leave.student_id != self.student_id:
            errors["boarding_leave"] = "The leave record must belong to the selected student."
        if errors:
            raise ValidationError(errors)


class WelfareCase(models.Model):
    HEALTH = "HEALTH"
    SAFEGUARDING = "SAFEGUARDING"
    DISCIPLINE = "DISCIPLINE"
    BOARDING = "BOARDING"
    EMOTIONAL = "EMOTIONAL"
    FAMILY = "FAMILY"
    ACADEMIC = "ACADEMIC"
    OTHER = "OTHER"

    CATEGORY_CHOICES = (
        (HEALTH, "Health"),
        (SAFEGUARDING, "Safeguarding"),
        (DISCIPLINE, "Discipline"),
        (BOARDING, "Boarding"),
        (EMOTIONAL, "Emotional wellbeing"),
        (FAMILY, "Family or home"),
        (ACADEMIC, "Academic support"),
        (OTHER, "Other"),
    )

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    SEVERITY_CHOICES = (
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
        (CRITICAL, "Critical"),
    )

    OPEN = "OPEN"
    MONITORING = "MONITORING"
    REFERRED = "REFERRED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

    STATUS_CHOICES = (
        (OPEN, "Open"),
        (MONITORING, "Monitoring"),
        (REFERRED, "Referred"),
        (RESOLVED, "Resolved"),
        (CLOSED, "Closed"),
    )

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="welfare_cases",
    )
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_cases",
    )
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default=OTHER)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default=MEDIUM)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    confidential = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_cases_assigned",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_cases_opened",
    )
    due_date = models.DateField(null=True, blank=True)
    linked_sickbay_visit = models.ForeignKey(
        "sickbay.SickbayVisit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_cases",
    )
    linked_discipline_incident = models.ForeignKey(
        "discipline.Incident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_cases",
    )
    linked_bed_allocation = models.ForeignKey(
        BedAllocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_cases",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["campus", "status", "severity"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.title}"

    def clean(self):
        super().clean()
        errors = {}
        if self.linked_sickbay_visit_id and self.student_id:
            if self.linked_sickbay_visit.student_id != self.student_id:
                errors["linked_sickbay_visit"] = "The sickbay visit must belong to the selected student."
        if self.linked_discipline_incident_id and self.student_id:
            if self.linked_discipline_incident.student_id != self.student_id:
                errors["linked_discipline_incident"] = "The discipline incident must belong to the selected student."
        if self.linked_bed_allocation_id and self.student_id:
            if self.linked_bed_allocation.student_id != self.student_id:
                errors["linked_bed_allocation"] = "The allocation must belong to the selected student."
        if self.status in {self.RESOLVED, self.CLOSED} and not self.resolution_summary:
            errors["resolution_summary"] = "Provide a resolution summary before resolving or closing the case."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.student_id and not self.campus_id:
            self.campus = self.student.campus
        if self.status in {self.RESOLVED, self.CLOSED} and not self.resolved_at:
            self.resolved_at = timezone.now()
        if self.status not in {self.RESOLVED, self.CLOSED}:
            self.resolved_at = None
        super().save(*args, **kwargs)


class WelfareCaseAction(models.Model):
    NOTE = "NOTE"
    FOLLOW_UP = "FOLLOW_UP"
    CONTACT = "CONTACT"
    REFERRAL = "REFERRAL"
    ESCALATION = "ESCALATION"
    RESOLUTION = "RESOLUTION"

    ACTION_CHOICES = (
        (NOTE, "Note"),
        (FOLLOW_UP, "Follow-up"),
        (CONTACT, "Parent or guardian contact"),
        (REFERRAL, "Referral"),
        (ESCALATION, "Escalation"),
        (RESOLUTION, "Resolution"),
    )

    welfare_case = models.ForeignKey(WelfareCase, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=16, choices=ACTION_CHOICES, default=NOTE)
    note = models.TextField()
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_case_actions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.welfare_case} - {self.get_action_type_display()}"
