from typing import Optional

from django import forms
from django.contrib.auth.hashers import check_password
from django.db.models import Q

from apps.tenant.students.models import StudentProfile

from .models import ParentProfile, ParentStudentLink


GUARDIAN_RELATIONSHIP_CHOICES = (
    ("", "Select relationship"),
    ("Mother", "Mother"),
    ("Father", "Father"),
    ("Guardian", "Guardian"),
    ("Grandparent", "Grandparent"),
    ("Sibling", "Sibling"),
    ("Sponsor", "Sponsor"),
    ("Other", "Other"),
)


class ParentCommunicationPreferencesForm(forms.ModelForm):
    """Parent-facing SMS/WhatsApp consent toggles."""

    class Meta:
        model = ParentProfile
        fields = [
            "allow_sms_alerts",
            "allow_whatsapp_alerts",
            "digest_enabled",
            "digest_email_enabled",
            "digest_whatsapp_enabled",
            "digest_pwa_enabled",
        ]
        labels = {
            "allow_sms_alerts": "Text message (SMS) alerts",
            "allow_whatsapp_alerts": "WhatsApp alerts",
            "digest_enabled": "Weekly Smart Parent Digest",
            "digest_email_enabled": "Email weekly digest",
            "digest_whatsapp_enabled": "WhatsApp weekly digest",
            "digest_pwa_enabled": "Browser/PWA weekly digest alert",
        }
        help_texts = {
            "allow_sms_alerts": "Fee reminders, absence notices, and urgent school messages sent by SMS.",
            "allow_whatsapp_alerts": "Same types of messages on WhatsApp when your school uses it.",
            "digest_enabled": "A weekly family summary covering attendance, fees, coursework, discipline, announcements and exams.",
            "digest_email_enabled": "Send the weekly digest to your email address.",
            "digest_whatsapp_enabled": "Send the weekly digest to your WhatsApp number when enabled by the school.",
            "digest_pwa_enabled": "Show a browser notification when the weekly digest is ready.",
        }
        widgets = {
            "allow_sms_alerts": forms.CheckboxInput(
                attrs={"class": "mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"}
            ),
            "allow_whatsapp_alerts": forms.CheckboxInput(
                attrs={"class": "mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"}
            ),
            "digest_enabled": forms.CheckboxInput(
                attrs={"class": "mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"}
            ),
            "digest_email_enabled": forms.CheckboxInput(
                attrs={"class": "mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"}
            ),
            "digest_whatsapp_enabled": forms.CheckboxInput(
                attrs={"class": "mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"}
            ),
            "digest_pwa_enabled": forms.CheckboxInput(
                attrs={"class": "mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"}
            ),
        }


class ParentProfileForm(forms.ModelForm):
    create_user = forms.BooleanField(required=False, initial=True)
    send_email = forms.BooleanField(required=False, initial=True)
    results_pin = forms.CharField(
        label="Results portal PIN (optional)",
        required=False,
        max_length=6,
        widget=forms.PasswordInput(render_value=False),
        help_text="4–6 digits. Parent must enter this to view published assessment results. Leave blank to keep unchanged.",
    )
    clear_results_pin = forms.BooleanField(
        label="Remove results PIN",
        required=False,
        help_text="If checked, parents can view results without an extra PIN.",
    )

    class Meta:
        model = ParentProfile
        fields = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "allow_sms_alerts",
            "allow_whatsapp_alerts",
            "digest_enabled",
            "digest_email_enabled",
            "digest_whatsapp_enabled",
            "digest_pwa_enabled",
            "is_active",
        ]

    def __init__(
        self,
        *args,
        campus_scope=None,
        include_student_link: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if include_student_link:
            students = StudentProfile.objects.filter(is_active=True).order_by(
                "last_name", "first_name", "student_id"
            )
            if campus_scope is not None:
                students = students.filter(campus=campus_scope)
            self.fields["student"] = forms.ModelChoiceField(
                label="Student cared for",
                queryset=students,
                required=True,
                help_text="Select the learner this parent or guardian is responsible for.",
            )
            self.fields["relationship"] = forms.ChoiceField(
                label="Relationship to student",
                choices=GUARDIAN_RELATIONSHIP_CHOICES,
                required=True,
            )
            self.fields["is_primary_guardian"] = forms.BooleanField(
                label="Primary guardian for this student",
                required=False,
                initial=True,
            )

    def clean_results_pin(self):
        pin = (self.cleaned_data.get("results_pin") or "").strip()
        if not pin:
            return ""
        if not pin.isdigit():
            raise forms.ValidationError("PIN must contain digits only.")
        if len(pin) < 4 or len(pin) > 6:
            raise forms.ValidationError("PIN must be 4 to 6 digits.")
        return pin


class ParentResultsPinSelfServiceForm(forms.Form):
    """Parent portal: set, change, or clear the optional results-view PIN."""

    current_pin = forms.CharField(
        label="Current PIN",
        required=False,
        max_length=6,
        widget=forms.PasswordInput(render_value=False),
    )
    new_pin = forms.CharField(
        label="New PIN",
        required=False,
        max_length=6,
        widget=forms.PasswordInput(render_value=False),
        help_text="4–6 digits. Leave blank if you only want to remove the PIN.",
    )
    confirm_pin = forms.CharField(
        label="Confirm new PIN",
        required=False,
        max_length=6,
        widget=forms.PasswordInput(render_value=False),
    )
    clear_pin = forms.BooleanField(label="Remove my results PIN", required=False)

    def __init__(self, *args, parent_profile: Optional[ParentProfile] = None, **kwargs):
        self.parent_profile = parent_profile
        super().__init__(*args, **kwargs)
        pin_widget_class = (
            "w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 "
            "shadow-sm focus:border-primary-500 focus:ring-primary-500"
        )
        for name in ("current_pin", "new_pin", "confirm_pin"):
            self.fields[name].widget.attrs.setdefault("class", pin_widget_class)

    def clean_new_pin(self):
        pin = (self.cleaned_data.get("new_pin") or "").strip()
        if not pin:
            return ""
        if not pin.isdigit():
            raise forms.ValidationError("PIN must contain digits only.")
        if len(pin) < 4 or len(pin) > 6:
            raise forms.ValidationError("PIN must be 4 to 6 digits.")
        return pin

    def clean(self):
        data = super().clean()
        if not self.parent_profile:
            return data

        clear = data.get("clear_pin")
        new = (data.get("new_pin") or "").strip()
        confirm = (data.get("confirm_pin") or "").strip()
        current = (data.get("current_pin") or "").strip()
        existing = self.parent_profile.results_access_pin_hash

        if clear and new:
            raise forms.ValidationError("Remove the PIN or set a new one — not both in the same request.")

        if clear:
            if not existing:
                raise forms.ValidationError("You do not have a PIN set.")
            if not current or not check_password(current, existing):
                self.add_error("current_pin", "Enter your current PIN to remove it.")
            return data

        if new:
            if new != confirm:
                self.add_error("confirm_pin", "New PIN and confirmation do not match.")
            if existing:
                if not current or not check_password(current, existing):
                    self.add_error("current_pin", "Enter your current PIN to change it.")
            return data

        raise forms.ValidationError(
            "Choose an action: enter a new PIN and confirmation, or tick “Remove my results PIN”."
        )


class ParentStudentLinkForm(forms.ModelForm):
    student = forms.ModelChoiceField(
        label="Student",
        queryset=StudentProfile.objects.filter(is_active=True).order_by(
            "last_name", "first_name", "student_id"
        ),
    )
    relationship = forms.ChoiceField(
        label="Relationship",
        choices=GUARDIAN_RELATIONSHIP_CHOICES,
        required=True,
    )
    is_primary = forms.BooleanField(
        label="Primary guardian",
        required=False,
    )

    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campus_scope is not None:
            self.fields["student"].queryset = self.fields["student"].queryset.filter(
                campus=campus_scope
            )

    class Meta:
        model = ParentStudentLink
        fields = [
            "student",
            "relationship",
            "is_primary",
        ]


class StudentGuardianLinkForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        label="Parent or guardian",
        queryset=ParentProfile.objects.filter(is_active=True).order_by(
            "last_name", "first_name"
        ),
    )
    relationship = forms.ChoiceField(
        label="Relationship",
        choices=GUARDIAN_RELATIONSHIP_CHOICES,
        required=True,
    )
    is_primary = forms.BooleanField(
        label="Primary guardian",
        required=False,
    )

    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campus_scope is not None:
            self.fields["parent"].queryset = (
                self.fields["parent"].queryset.filter(
                    Q(parentstudentlink__student__campus=campus_scope)
                    | Q(parentstudentlink__isnull=True)
                )
                .distinct()
                .order_by("last_name", "first_name")
            )

    class Meta:
        model = ParentStudentLink
        fields = [
            "parent",
            "relationship",
            "is_primary",
        ]
