from django import forms

from apps.tenant.parents.models import ParentProfile

from .hardening_models import GuardianContactLog, WelfareCaseEscalation


class GuardianContactLogForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        label="Linked parent or guardian",
        queryset=ParentProfile.objects.none(),
        required=False,
        help_text="Choose from the parents already linked to this student.",
    )

    class Meta:
        model = GuardianContactLog
        fields = [
            "parent",
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
        student = kwargs.pop("student", None)
        default_name = kwargs.pop("default_name", "")
        default_phone = kwargs.pop("default_phone", "")
        default_purpose = kwargs.pop("default_purpose", "")
        super().__init__(*args, **kwargs)

        queryset = ParentProfile.objects.none()
        primary_parent = None
        if student is not None:
            queryset = ParentProfile.objects.filter(
                parentstudentlink__student=student,
                is_active=True,
            ).distinct().order_by("last_name", "first_name")
            primary_parent = queryset.filter(
                parentstudentlink__student=student,
                parentstudentlink__is_primary=True,
            ).first()
        self.fields["parent"].queryset = queryset

        if not self.is_bound:
            if primary_parent:
                self.fields["parent"].initial = primary_parent
                default_name = default_name or str(primary_parent)
                default_phone = default_phone or primary_parent.phone
            self.fields["contact_name"].initial = default_name
            self.fields["contact_phone"].initial = default_phone
            if default_purpose:
                self.fields["purpose"].initial = default_purpose

    def clean(self):
        cleaned = super().clean()
        parent = cleaned.get("parent")
        if parent:
            if not (cleaned.get("contact_name") or "").strip():
                cleaned["contact_name"] = str(parent)
            if not (cleaned.get("contact_phone") or "").strip():
                cleaned["contact_phone"] = parent.phone or ""
        return cleaned


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
