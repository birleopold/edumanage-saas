from django import forms

from .hardening_models import GuardianContactLog, WelfareCaseEscalation


class GuardianContactLogForm(forms.ModelForm):
    class Meta:
        model = GuardianContactLog
        fields = [
            "purpose",
            "method",
            "outcome",
            "contact_name",
            "contact_phone",
            "occurred_at",
            "note",
        ]
        widgets = {
            "occurred_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        default_name = kwargs.pop("default_name", "")
        default_phone = kwargs.pop("default_phone", "")
        default_purpose = kwargs.pop("default_purpose", "")
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["contact_name"].initial = default_name
            self.fields["contact_phone"].initial = default_phone
            if default_purpose:
                self.fields["purpose"].initial = default_purpose


class WelfareCaseEscalationForm(forms.ModelForm):
    class Meta:
        model = WelfareCaseEscalation
        fields = [
            "level",
            "response_due_at",
            "reason",
            "guardian_contact_required",
        ]
        widgets = {
            "response_due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }
