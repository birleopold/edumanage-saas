from decimal import Decimal

from django import forms

from apps.tenant.students.models import StudentProfile

from .models import AssetAssignment, InventoryItem, StockMovement


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ["sku", "name", "unit", "is_active"]


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ["item", "movement_type", "quantity", "reference", "note"]

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty is None:
            return qty
        if qty <= 0:
            raise forms.ValidationError("Quantity must be greater than 0.")
        return qty

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        movement_type = cleaned.get("movement_type")
        quantity = cleaned.get("quantity") or Decimal("0")
        if item and movement_type == StockMovement.OUT and quantity > item.stock_on_hand():
            self.add_error("quantity", "Stock out quantity cannot exceed stock on hand.")
        return cleaned


class AssetAssignmentForm(forms.ModelForm):
    class Meta:
        model = AssetAssignment
        fields = [
            "item",
            "quantity",
            "assigned_to_user",
            "assigned_to_student",
            "assigned_at",
            "returned_at",
            "status",
            "note",
        ]
        widgets = {
            "assigned_at": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "returned_at": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)
        self.fields["assigned_to_student"].queryset = StudentProfile.objects.select_related("campus").all()
        if campus_scope:
            self.fields["assigned_to_student"].queryset = self.fields["assigned_to_student"].queryset.filter(campus=campus_scope)

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty is not None and qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return qty

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        quantity = cleaned.get("quantity") or Decimal("0")
        user = cleaned.get("assigned_to_user")
        student = cleaned.get("assigned_to_student")
        assigned_at = cleaned.get("assigned_at")
        returned_at = cleaned.get("returned_at")
        status = cleaned.get("status")

        if not user and not student:
            raise forms.ValidationError("Assign to a user or a student.")
        if user and student:
            raise forms.ValidationError("Choose only one assignee: user or student.")
        if assigned_at and returned_at and returned_at < assigned_at:
            self.add_error("returned_at", "Return date cannot be before assignment date.")
        if status == AssetAssignment.RETURNED and not returned_at:
            self.add_error("returned_at", "Returned assignments must have a return date.")
        if status == AssetAssignment.ACTIVE and returned_at:
            self.add_error("returned_at", "Active assignments should not have a return date.")
        if item and status == AssetAssignment.ACTIVE:
            active_assigned = AssetAssignment.objects.filter(item=item, status=AssetAssignment.ACTIVE)
            if self.instance and self.instance.pk:
                active_assigned = active_assigned.exclude(pk=self.instance.pk)
            active_quantity = sum((a.quantity or Decimal("0")) for a in active_assigned)
            available = item.stock_on_hand() - active_quantity
            if quantity > available:
                self.add_error("quantity", f"Only {available} {item.unit or 'units'} available for assignment.")
        return cleaned
