from django import forms

from .models import IntegrationProviderConfig, IntegrationScope


class ProviderForm(forms.ModelForm):
    class Meta:
        model = IntegrationProviderConfig
        fields = ["name", "provider_type", "base_url", "client_id", "access_token", "webhook_secret", "settings", "is_active"]
        widgets = {"settings": forms.Textarea(attrs={"rows": 4})}


class ScopePickerForm(forms.Form):
    name = forms.CharField(max_length=120, required=False)
    scopes = forms.ModelMultipleChoiceField(queryset=IntegrationScope.objects.filter(is_active=True), widget=forms.CheckboxSelectMultiple, required=False)
