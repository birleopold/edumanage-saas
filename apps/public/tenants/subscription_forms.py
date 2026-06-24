from django import forms

from .models import SubscriptionPlan, TenantSubscription
from .subscription_services import ensure_default_plans


class SubscriptionFormMixin:
    default_input_class = (
        "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 "
        "text-sm font-semibold text-slate-900 shadow-sm outline-none "
        "focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
    )

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {self.default_input_class}".strip()


class TenantSubscriptionForm(SubscriptionFormMixin, forms.Form):
    plan = forms.ModelChoiceField(queryset=SubscriptionPlan.objects.none(), label="Package/plan")
    status = forms.ChoiceField(choices=TenantSubscription.STATUS_CHOICES)
    billing_cycle = forms.ChoiceField(choices=SubscriptionPlan.BILLING_CHOICES)
    payment_status = forms.ChoiceField(choices=TenantSubscription.PAYMENT_CHOICES)
    payment_reference = forms.CharField(required=False, max_length=120)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_default_plans()
        self.fields["plan"].queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "monthly_price")
        self._style_fields()


class SubscriptionInvoiceForm(SubscriptionFormMixin, forms.Form):
    due_on = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class SubscriptionPaymentForm(SubscriptionFormMixin, forms.Form):
    payment_reference = forms.CharField(required=True, max_length=120)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
