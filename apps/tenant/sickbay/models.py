from django.conf import settings
from django.db import models
from django.utils import timezone


class StudentMedicalProfile(models.Model):
    BLOOD_GROUP_CHOICES = (
        ("", "Unknown"),
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
    )

    student = models.OneToOneField("students.StudentProfile", on_delete=models.CASCADE, related_name="medical_profile")
    blood_group = models.CharField(max_length=4, choices=BLOOD_GROUP_CHOICES, blank=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    current_medication = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)
    preferred_clinic_or_doctor = models.CharField(max_length=180, blank=True)
    doctor_phone = models.CharField(max_length=32, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")

    def __str__(self) -> str:
        return f"Medical profile - {self.student}"

    @property
    def has_alerts(self) -> bool:
        return bool(self.allergies or self.chronic_conditions or self.current_medication)


class SickbayVisit(models.Model):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    SEVERITY_CHOICES = (
        (MILD, "Mild"),
        (MODERATE, "Moderate"),
        (SEVERE, "Severe"),
    )

    OBSERVATION = "OBSERVATION"
    TREATED = "TREATED"
    RETURNED_TO_CLASS = "RETURNED_TO_CLASS"
    SENT_HOME = "SENT_HOME"
    REFERRED = "REFERRED"
    EMERGENCY = "EMERGENCY"
    OUTCOME_CHOICES = (
        (OBSERVATION, "Under observation"),
        (TREATED, "Treated"),
        (RETURNED_TO_CLASS, "Returned to class"),
        (SENT_HOME, "Sent home"),
        (REFERRED, "Referred to clinic/hospital"),
        (EMERGENCY, "Emergency escalation"),
    )

    PARENT_METHOD_CHOICES = (
        ("", "Not notified"),
        ("PHONE", "Phone call"),
        ("SMS", "SMS"),
        ("WHATSAPP", "WhatsApp"),
        ("PORTAL", "Portal message"),
        ("IN_PERSON", "In person"),
    )

    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="sickbay_visits")
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    visit_at = models.DateTimeField(default=timezone.now)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default=MILD)
    complaint = models.CharField(max_length=200)
    symptoms = models.TextField(blank=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    attended_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sickbay_visits_attended")
    nurse_or_doctor_name = models.CharField(max_length=150, blank=True)
    treatment_given = models.TextField(blank=True)
    medicine_given = models.CharField(max_length=200, blank=True)
    dosage = models.CharField(max_length=120, blank=True)
    parent_notified = models.BooleanField(default=False)
    parent_notified_at = models.DateTimeField(null=True, blank=True)
    parent_notification_method = models.CharField(max_length=16, choices=PARENT_METHOD_CHOICES, blank=True)
    outcome = models.CharField(max_length=24, choices=OUTCOME_CHOICES, default=OBSERVATION)
    follow_up_required = models.BooleanField(default=False)
    follow_up_note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sickbay_visits_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-visit_at", "-created_at")
        indexes = [
            models.Index(fields=["student", "visit_at"]),
            models.Index(fields=["campus", "visit_at"]),
            models.Index(fields=["outcome", "visit_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.complaint} ({self.visit_at:%Y-%m-%d})"

    def save(self, *args, **kwargs):
        if self.student_id and not self.campus_id:
            self.campus = self.student.campus
        if self.parent_notified and not self.parent_notified_at:
            self.parent_notified_at = timezone.now()
        if not self.parent_notified:
            self.parent_notified_at = None
            self.parent_notification_method = ""
        super().save(*args, **kwargs)
