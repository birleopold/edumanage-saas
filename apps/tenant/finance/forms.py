from django import forms

from apps.tenant.students.models import StudentProfile

from .models import FeeItem, Invoice, InvoiceLine, Payment


class FeeItemForm(forms.ModelForm):
    class Meta:
        model = FeeItem
        fields = ["code", "name", "amount", "is_active"]


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "student",
            "academic_year",
            "academic_term",
            "reference",
            "due_date",
            "status",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)
        if campus is not None:
            self.fields["student"].queryset = StudentProfile.objects.filter(campus=campus)


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["fee_item", "description", "quantity", "unit_amount"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference", "received_at"]
        widgets = {
            "received_at": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
        }
