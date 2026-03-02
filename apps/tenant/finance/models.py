from decimal import Decimal

from django.db import models


class FeeItem(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.code else self.name


class Invoice(models.Model):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (CLOSED, "Closed"),
    )

    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reference = models.CharField(max_length=64, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Invoice #{self.id}"

    def total_amount(self) -> Decimal:
        total = Decimal("0")
        for line in self.lines.all():
            total += line.line_total()
        return total

    def total_paid(self) -> Decimal:
        total = Decimal("0")
        for p in self.payments.all():
            total += p.amount
        return total

    def balance(self) -> Decimal:
        return self.total_amount() - self.total_paid()


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    fee_item = models.ForeignKey(FeeItem, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return self.description

    def line_total(self) -> Decimal:
        return (self.quantity or Decimal("0")) * (self.unit_amount or Decimal("0"))


class Payment(models.Model):
    CASH = "CASH"
    BANK = "BANK"
    MOBILE = "MOBILE"
    CARD = "CARD"

    METHOD_CHOICES = (
        (CASH, "Cash"),
        (BANK, "Bank"),
        (MOBILE, "Mobile money"),
        (CARD, "Card"),
    )

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default=CASH)
    reference = models.CharField(max_length=128, blank=True)
    received_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.invoice} payment {self.amount}"
