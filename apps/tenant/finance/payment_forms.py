from django import forms

from .models import Payment


class ParentPaymentInitiationForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=1)
    phone_number = forms.CharField(max_length=32)
    network = forms.ChoiceField(choices=((Payment.MTN_MOMO, "MTN MoMo"), (Payment.AIRTEL_MONEY, "Airtel Money")))

    def clean_phone_number(self):
        return (self.cleaned_data.get("phone_number") or "").strip()
