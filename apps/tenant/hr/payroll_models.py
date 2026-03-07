from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class PayGrade(models.Model):
    name = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=32, unique=True)
    min_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    max_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class SalaryStructure(models.Model):
    staff = models.OneToOneField("hr.StaffProfile", on_delete=models.CASCADE, related_name="salary_structure")
    pay_grade = models.ForeignKey(PayGrade, on_delete=models.SET_NULL, null=True, blank=True)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    effective_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-effective_date",)

    def __str__(self) -> str:
        return f"{self.staff} - {self.base_salary}"


class AllowanceType(models.Model):
    name = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=32, unique=True)
    is_taxable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class DeductionType(models.Model):
    name = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=32, unique=True)
    is_percentage = models.BooleanField(default=False)
    default_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Default rate (% or fixed amount)",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Payslip(models.Model):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"

    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (PENDING_APPROVAL, "Pending Approval"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (PAID, "Paid"),
    )

    staff = models.ForeignKey("hr.StaffProfile", on_delete=models.CASCADE, related_name="payslips")
    period_year = models.IntegerField()
    period_month = models.IntegerField()
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    gross_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))]
    )
    total_allowances = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))]
    )
    total_deductions = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))]
    )
    net_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_payslips"
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_payslips",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-period_year", "-period_month", "staff")
        unique_together = (("staff", "period_year", "period_month"),)

    def __str__(self) -> str:
        return f"{self.staff} - {self.period_year}/{self.period_month:02d}"

    def calculate_totals(self):
        self.total_allowances = sum(a.amount for a in self.allowances.all())
        self.total_deductions = sum(d.amount for d in self.deductions.all())
        self.gross_salary = self.base_salary + self.total_allowances
        self.net_salary = self.gross_salary - self.total_deductions


class PayslipAllowance(models.Model):
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="allowances")
    allowance_type = models.ForeignKey(AllowanceType, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])

    class Meta:
        ordering = ("allowance_type__name",)

    def __str__(self) -> str:
        return f"{self.payslip} - {self.allowance_type}: {self.amount}"


class PayslipDeduction(models.Model):
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="deductions")
    deduction_type = models.ForeignKey(DeductionType, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])

    class Meta:
        ordering = ("deduction_type__name",)

    def __str__(self) -> str:
        return f"{self.payslip} - {self.deduction_type}: {self.amount}"


class PayrollApproval(models.Model):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    )

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="approvals")
    approver_role = models.CharField(
        max_length=32, help_text="Role required for this approval (e.g., ADMIN, PRINCIPAL)"
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_approvals"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    approved_at = models.DateTimeField(null=True, blank=True)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.payslip} - {self.approver_role}: {self.status}"
