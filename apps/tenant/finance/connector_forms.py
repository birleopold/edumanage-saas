from django import forms

from .models import IntegrationProviderConfig, IntegrationScope


class ProviderForm(forms.ModelForm):
    class Meta:
        model = IntegrationProviderConfig
        fields = [
            "name",
            "provider_type",
            "base_url",
            "client_id",
            "client_secret",
            "access_token",
            "webhook_secret",
            "settings",
            "is_active",
        ]
        widgets = {
            "client_secret": forms.PasswordInput(render_value=True),
            "access_token": forms.PasswordInput(render_value=True),
            "webhook_secret": forms.PasswordInput(render_value=True),
            "settings": forms.Textarea(attrs={"rows": 4}),
        }


class ScopePickerForm(forms.Form):
    name = forms.CharField(max_length=120, required=False)
    scopes = forms.ModelMultipleChoiceField(queryset=IntegrationScope.objects.filter(is_active=True), widget=forms.CheckboxSelectMultiple, required=False)
