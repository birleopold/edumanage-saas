from django import forms

from .models import SickbayVisit, StudentMedicalProfile


class StudentMedicalProfileForm(forms.ModelForm):
    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campus_scope is not None:
            self.fields["student"].queryset = self.fields["student"].queryset.filter(campus=campus_scope)

    class Meta:
        model = StudentMedicalProfile
        fields = [
            "student",
            "blood_group",
            "allergies",
            "chronic_conditions",
            "current_medication",
            "emergency_contact_name",
            "emergency_contact_phone",
            "preferred_clinic_or_doctor",
            "doctor_phone",
            "notes",
        ]


class SickbayVisitForm(forms.ModelForm):
    visit_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campus_scope is not None:
            self.fields["student"].queryset = self.fields["student"].queryset.filter(campus=campus_scope)

    class Meta:
        model = SickbayVisit
        fields = [
            "student",
            "visit_at",
            "severity",
            "complaint",
            "symptoms",
            "temperature_c",
            "nurse_or_doctor_name",
            "treatment_given",
            "medicine_given",
            "dosage",
            "parent_notified",
            "parent_notification_method",
            "outcome",
            "follow_up_required",
            "follow_up_note",
        ]
        widgets = {
            "symptoms": forms.Textarea(attrs={"rows": 3}),
            "treatment_given": forms.Textarea(attrs={"rows": 3}),
            "follow_up_note": forms.Textarea(attrs={"rows": 3}),
        }
