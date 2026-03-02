from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum


class InventoryItem(models.Model):
    sku = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["sku"],
                condition=~models.Q(sku=""),
                name="uniq_inventory_sku_nonblank",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def stock_on_hand(self) -> Decimal:
        totals = self.movements.aggregate(
            in_qty=Sum("quantity", filter=models.Q(movement_type=StockMovement.IN)),
            out_qty=Sum("quantity", filter=models.Q(movement_type=StockMovement.OUT)),
            adj_qty=Sum("quantity", filter=models.Q(movement_type=StockMovement.ADJUST)),
        )
        in_qty = totals.get("in_qty") or Decimal("0")
        out_qty = totals.get("out_qty") or Decimal("0")
        adj_qty = totals.get("adj_qty") or Decimal("0")
        return in_qty - out_qty + adj_qty


class StockMovement(models.Model):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"

    MOVEMENT_CHOICES = (
        (IN, "Stock In"),
        (OUT, "Stock Out"),
        (ADJUST, "Adjust"),
    )

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=16, choices=MOVEMENT_CHOICES, default=IN)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=128, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.item} {self.movement_type} {self.quantity}"


class AssetAssignment(models.Model):
    ACTIVE = "ACTIVE"
    RETURNED = "RETURNED"

    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (RETURNED, "Returned"),
    )

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    assigned_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    assigned_to_student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    assigned_at = models.DateField(null=True, blank=True)
    returned_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_asset_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.item} x{self.quantity}"
