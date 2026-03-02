from django import forms

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

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("assigned_to_user")
        student = cleaned.get("assigned_to_student")
        if not user and not student:
            raise forms.ValidationError("Assign to a user or a student.")
        if user and student:
            raise forms.ValidationError("Choose only one assignee: user or student.")
        return cleaned
