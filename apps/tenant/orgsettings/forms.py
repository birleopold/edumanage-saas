from django import forms

from .models import Campus, FeatureFlag, OrganizationProfile


class OrganizationProfileForm(forms.ModelForm):
    class Meta:
        model = OrganizationProfile
        fields = [
            "name",
            "legal_name",
            "email",
            "phone",
            "address",
            "default_currency",
            "logo",
            "primary_color",
            "secondary_color",
        ]
        widgets = {
            "primary_color": forms.TextInput(attrs={
                "type": "color",
                "class": "h-10 w-20 rounded border border-gray-300 cursor-pointer",
            }),
            "secondary_color": forms.TextInput(attrs={
                "type": "color",
                "class": "h-10 w-20 rounded border border-gray-300 cursor-pointer",
            }),
        }


class CampusForm(forms.ModelForm):
    class Meta:
        model = Campus
        fields = [
            "name",
            "code",
            "email",
            "phone",
            "address",
            "student_number_format",
            "logo_override",
            "primary_color_override",
            "secondary_color_override",
            "is_active",
            "is_default",
        ]
        help_texts = {
            "student_number_format": (
                "Examples: 10/u/00 produces 10/u/00, 10/u/01, 10/u/02; "
                "or use {CAMPUS_CODE}-{YYYY}-{SEQ:5}. Leave blank for the default."
            ),
        }
        widgets = {
            "student_number_format": forms.TextInput(attrs={
                "placeholder": "Example: 10/u/00",
            }),
            "primary_color_override": forms.TextInput(attrs={
                "type": "color",
                "class": "h-10 w-20 rounded border border-gray-300 cursor-pointer",
            }),
            "secondary_color_override": forms.TextInput(attrs={
                "type": "color",
                "class": "h-10 w-20 rounded border border-gray-300 cursor-pointer",
            }),
        }


class FeatureFlagForm(forms.ModelForm):
    class Meta:
        model = FeatureFlag
        fields = ["code", "is_enabled", "campus"]
