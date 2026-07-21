from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class GuardianContactLog(models.Model):
    LEAVE_APPROVAL = "LEAVE_APPROVAL"
    DEPARTURE = "DEPARTURE"
    RETURN = "RETURN"
    ABSENCE = "ABSENCE"
    WELFARE = "WELFARE"
    EMERGENCY = "EMERGENCY"
    GENERAL = "GENERAL"

    PURPOSE_CHOICES = (
        (LEAVE_APPROVAL, "Leave approval or confirmation"),
        (DEPARTURE, "Departure handover"),
        (RETURN, "Return confirmation"),
        (ABSENCE, "Roll-call absence follow-up"),
        (WELFARE, "Welfare follow-up"),
        (EMERGENCY, "Emergency contact"),
        (GENERAL, "General boarding contact"),
    )

    PHONE = "PHONE"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    PORTAL = "PORTAL"
    IN_PERSON = "IN_PERSON"
    EMAIL = "EMAIL"
    OTHER = "OTHER"

    METHOD_CHOICES = (
        (PHONE, "Phone call"),
        (SMS, "SMS"),
        (WHATSAPP, "WhatsApp"),
        (PORTAL, "Parent portal"),
        (IN_PERSON, "In person"),
        (EMAIL, "Email"),
        (OTHER, "Other"),
    )

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REACHED = "REACHED"
    MESSAGE_LEFT = "MESSAGE_LEFT"
    NO_ANSWER = "NO_ANSWER"
    WRONG_NUMBER = "WRONG_NUMBER"
    DECLINED = "DECLINED"

    OUTCOME_CHOICES = (
        (PENDING, "Pending response"),
        (CONFIRMED, "Confirmed"),
        (REACHED, "Reached"),
        (MESSAGE_LEFT, "Message left"),
        (NO_ANSWER, "No answer"),
        (WRONG_NUMBER, "Wrong number"),
        (DECLINED, "Declined or not authorised"),
    )

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="guardian_contact_logs",
    )
    boarding_leave = models.ForeignKey(
        "hostels.BoardingLeave",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guardian_contact_logs",
    )
    welfare_case = models.ForeignKey(
        "hostels.WelfareCase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guardian_contact_logs",
    )
    roll_call_entry = models.ForeignKey(
        "hostels.HostelRollCallEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guardian_contact_logs",
    )
    purpose = models.CharField(max_length=24, choices=PURPOSE_CHOICES, default=GENERAL)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default=PHONE)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default=PENDING)
    contact_name = models.CharField(max_length=150, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guardian_contact_logs_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-created_at")
        indexes = [
            models.Index(fields=["student", "occurred_at"]),
            models.Index(fields=["outcome", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.get_purpose_display()} ({self.get_outcome_display()})"

    def clean(self):
        super().clean()
        errors = {}
        for field_name in ("boarding_leave", "welfare_case", "roll_call_entry"):
            source = getattr(self, field_name, None)
            if source and source.student_id != self.student_id:
                errors[field_name] = "The linked record must belong to the selected student."
        if self.outcome in {self.CONFIRMED, self.REACHED} and not (self.contact_name or self.contact_phone):
            errors["contact_name"] = "Record the contacted person or phone number for a successful contact."
        if errors:
            raise ValidationError(errors)

    @property
    def is_confirmation(self):
        return self.outcome == self.CONFIRMED


class WelfareCaseEscalation(models.Model):
    NONE = "NONE"
    STAFF = "STAFF"
    SENIOR = "SENIOR"
    SAFEGUARDING = "SAFEGUARDING"
    EMERGENCY = "EMERGENCY"

    LEVEL_CHOICES = (
        (NONE, "No escalation"),
        (STAFF, "Assigned staff follow-up"),
        (SENIOR, "Senior management"),
        (SAFEGUARDING, "Safeguarding lead"),
        (EMERGENCY, "Emergency response"),
    )

    welfare_case = models.OneToOneField(
        "hostels.WelfareCase",
        on_delete=models.CASCADE,
        related_name="operational_escalation",
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=NONE)
    response_due_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    guardian_contact_required = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welfare_case_escalations",
    )
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-escalated_at", "-updated_at")

    def __str__(self):
        return f"{self.welfare_case} - {self.get_level_display()}"

    def clean(self):
        super().clean()
        if self.level != self.NONE and not self.reason.strip():
            raise ValidationError({"reason": "Provide a reason for the escalation."})

    @property
    def is_response_overdue(self):
        return bool(
            self.response_due_at
            and self.response_due_at < timezone.now()
            and self.welfare_case.status not in {
                self.welfare_case.RESOLVED,
                self.welfare_case.CLOSED,
            }
        )
