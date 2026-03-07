from django.conf import settings
from django.db import models


class Department(models.Model):
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        unique_together = (
            ("campus", "name"),
        )

    def __str__(self) -> str:
        return self.name


class Position(models.Model):
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("title",)
        unique_together = (
            ("department", "title"),
        )

    def __str__(self) -> str:
        return self.title


class StaffProfile(models.Model):
    TEACHING = "TEACHING"
    NON_TEACHING = "NON_TEACHING"

    STAFF_CATEGORY_CHOICES = (
        (TEACHING, "Teaching"),
        (NON_TEACHING, "Non-teaching"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_profile",
    )

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    staff_id = models.CharField(max_length=64, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)

    staff_category = models.CharField(
        max_length=16,
        choices=STAFF_CATEGORY_CHOICES,
        default=TEACHING,
    )

    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True)

    reports_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("last_name", "first_name")

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()


class DepartmentHead(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="heads")
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="headed_departments")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.department} -> {self.staff}"


# Import payroll models
from .payroll_models import (  # noqa: E402, F401
    AllowanceType,
    DeductionType,
    PayGrade,
    Payslip,
    PayslipAllowance,
    PayslipDeduction,
    PayrollApproval,
    SalaryStructure,
)
