from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
    )
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    stream = models.ForeignKey(
        "academics.Stream",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    student_id = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    district = models.CharField(max_length=128, blank=True)
    subcounty = models.CharField("Sub-county", max_length=128, blank=True)
    parish = models.CharField(max_length=128, blank=True)
    nin = models.CharField(
        "NIN",
        max_length=32,
        blank=True,
        help_text="National Identification Number (optional).",
    )
    learner_id = models.CharField(
        "Learner ID",
        max_length=64,
        blank=True,
        help_text="Government / EMIS learner identifier when applicable.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("last_name", "first_name")

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()
