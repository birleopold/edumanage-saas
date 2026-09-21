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
        labels = {
            "name": "School / institution name",
            "legal_name": "Registered / legal name (optional)",
            "email": "Main school email (optional)",
            "phone": "Main school phone (optional)",
            "address": "Main address (optional)",
            "default_currency": "School currency",
            "logo": "School logo (optional)",
            "primary_color": "Main brand colour (optional)",
            "secondary_color": "Second brand colour (optional)",
        }
        help_texts = {
            "name": "Use the name staff, learners and parents should see on EduManage records and reports.",
            "legal_name": "Enter this only when the registered name differs from the everyday school name.",
            "default_currency": "Use a three-letter currency code such as UGX, USD, KES or TZS. This is used on fees and financial reports.",
            "logo": "Optional during first setup. You can add or replace branding later.",
        }
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

    def clean_name(self):
        value = (self.cleaned_data.get("name") or "").strip()
        if not value:
            raise forms.ValidationError("Enter the school/institution name.")
        return value

    def clean_default_currency(self):
        value = (self.cleaned_data.get("default_currency") or "").strip().upper()
        if len(value) != 3 or not value.isalpha() or not value.isascii():
            raise forms.ValidationError(
                "Enter a three-letter currency code such as UGX, USD, KES or TZS."
            )
        return value


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
        labels = {
            "name": "Campus / school site name",
            "code": "Short campus code (optional)",
            "email": "Campus email (optional)",
            "phone": "Campus phone (optional)",
            "address": "Campus address (optional)",
            "student_number_format": "Student-number format (optional)",
            "logo_override": "Different campus logo (optional)",
            "primary_color_override": "Different main colour (optional)",
            "secondary_color_override": "Different second colour (optional)",
            "is_active": "This campus is currently in use",
            "is_default": "Use this as the default campus",
        }
        help_texts = {
            "name": "A campus is a physical or administrative school site, for example Main Campus or Annex. A one-site school normally needs only one campus.",
            "code": "Optional short identifier, for example MAIN or ANNEX. Keep it stable once records are in use.",
            "student_number_format": (
                "Optional. Leave blank to use the normal EduManage numbering. "
                "Only enter a custom pattern if the school already has a numbering convention."
            ),
            "logo_override": "Leave blank to use the institution logo.",
            "primary_color_override": "Leave unchanged/blank when this campus uses the main institution branding.",
            "secondary_color_override": "Leave unchanged/blank when this campus uses the main institution branding.",
            "is_active": "Inactive campuses are excluded from normal setup choices and cannot be used for new day-to-day records.",
            "is_default": "EduManage uses the default campus when a screen needs a campus and none has been chosen. There should normally be one default active campus.",
        }
        widgets = {
            "student_number_format": forms.TextInput(attrs={
                "placeholder": "Leave blank unless the school uses a custom format",
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

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization or getattr(self.instance, "organization", None)
        if self.organization and not self.is_bound and not self.instance.pk:
            has_active = Campus.objects.filter(
                organization=self.organization,
                is_active=True,
            ).exists()
            if not has_active:
                self.fields["is_default"].initial = True

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        if not self.organization:
            return cleaned

        is_active = bool(cleaned.get("is_active"))
        is_default = bool(cleaned.get("is_default"))
        if is_default and not is_active:
            self.add_error(
                "is_active",
                "A default campus must be active. Turn the campus on or choose another default campus first.",
            )
            return cleaned

        other_active = Campus.objects.filter(
            organization=self.organization,
            is_active=True,
        )
        other_default = other_active.filter(is_default=True)
        if self.instance.pk:
            other_active = other_active.exclude(pk=self.instance.pk)
            other_default = other_default.exclude(pk=self.instance.pk)

        if self.instance.pk and self.instance.is_active and not is_active and not other_active.exists():
            self.add_error(
                "is_active",
                "This is the institution's last active campus. Add or activate another campus before turning this one off.",
            )

        # Keep setup deterministic: whenever this is the only usable/default
        # campus candidate, make it the default rather than leaving the school
        # with an ambiguous campus-less state.
        if is_active and not is_default and not other_default.exists():
            cleaned["is_default"] = True
        return cleaned


class FeatureFlagForm(forms.ModelForm):
    class Meta:
        model = FeatureFlag
        fields = ["code", "is_enabled", "campus"]