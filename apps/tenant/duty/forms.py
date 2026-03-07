from django import forms

from .models import TeacherDutyRoster


class TeacherDutyRosterForm(forms.ModelForm):
    class Meta:
        model = TeacherDutyRoster
        fields = ["campus", "date", "duty_type", "teacher", "notes", "is_active"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }
