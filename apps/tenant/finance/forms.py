from django import forms

from apps.tenant.academics.models import AcademicTerm, AcademicYear
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
            "opening_balance",
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
        fields = ["amount", "method", "mobile_network", "reference", "received_at"]
        widgets = {
            "received_at": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("method") != Payment.MOBILE:
            cleaned["mobile_network"] = ""
        return cleaned


class CarryForwardForm(forms.Form):
    target_year = forms.ModelChoiceField(
        label="Target academic year",
        queryset=AcademicYear.objects.none(),
        required=True,
    )
    target_term = forms.ModelChoiceField(
        label="Target term",
        queryset=AcademicTerm.objects.select_related("year"),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_year"].queryset = AcademicYear.objects.all().order_by("-name")
        self.fields["target_term"].queryset = AcademicTerm.objects.select_related("year").order_by(
            "-year__name", "order"
        )

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("target_year")
        term = cleaned.get("target_term")
        if year and term and term.year_id != year.pk:
            raise forms.ValidationError("The selected term must belong to the selected academic year.")
        return cleaned
