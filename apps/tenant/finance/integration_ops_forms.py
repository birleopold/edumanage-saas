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
    scopes = forms.ModelMultipleChoiceField(
        queryset=IntegrationScope.objects.filter(is_active=True).order_by("code"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["class"] = self.field_class


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
