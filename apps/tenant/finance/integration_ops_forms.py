import ipaddress

from django import forms

from .models import IntegrationApiKey, IntegrationScope, WebhookEndpoint


class StyledFormMixin:
    field_class = (
        "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 text-sm "
        "font-semibold text-slate-900 outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-100"
    )

    def _style_fields(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", self.field_class)


class IntegrationApiKeyCreateForm(StyledFormMixin, forms.Form):
    name = forms.CharField(max_length=120)
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Optional. The key stops working automatically at this time.",
    )
    allowed_ip_addresses = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional comma-separated IPv4 or IPv6 addresses.",
    )
    scopes = forms.ModelMultipleChoiceField(
        queryset=IntegrationScope.objects.filter(is_active=True).order_by("code"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["class"] = self.field_class
        self.fields["expires_at"].widget.attrs["class"] = self.field_class
        self.fields["allowed_ip_addresses"].widget.attrs["class"] = self.field_class

    def clean_allowed_ip_addresses(self):
        raw = self.cleaned_data.get("allowed_ip_addresses") or ""
        addresses = []
        for value in (item.strip() for item in raw.replace("\n", ",").split(",")):
            if not value:
                continue
            try:
                normalized = str(ipaddress.ip_address(value))
            except ValueError as exc:
                raise forms.ValidationError(f"Invalid IP address: {value}") from exc
            if normalized not in addresses:
                addresses.append(normalized)
        return addresses


class WebhookEndpointForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WebhookEndpoint
        fields = ["name", "target_url", "event_type", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class IntegrationScopeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = IntegrationScope
        fields = ["code", "name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
