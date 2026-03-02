from django.db import models


class Applicant(models.Model):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"

    STATUS_CHOICES = (
        (NEW, "New"),
        (IN_REVIEW, "In review"),
        (ADMITTED, "Admitted"),
        (REJECTED, "Rejected"),
    )

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    target_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_level = models.ForeignKey(
        "academics.Level",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_class_group = models.ForeignKey(
        "academics.ClassGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=NEW)

    created_student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()
