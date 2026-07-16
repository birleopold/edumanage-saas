from django import forms

from .models import Incident, IncidentAction


class IncidentForm(forms.ModelForm):
    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campus_scope is not None:
            self.fields["student"].queryset = self.fields["student"].queryset.filter(campus=campus_scope)

    class Meta:
        model = Incident
        fields = [
            "student",
            "title",
            "category",
            "severity",
            "incident_date",
            "description",
            "status",
        ]
        widgets = {
            "incident_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }


class TeacherIncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = [
            "student",
            "title",
            "category",
            "severity",
            "incident_date",
            "description",
        ]
        widgets = {
            "incident_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }


class IncidentActionForm(forms.ModelForm):
    class Meta:
        model = IncidentAction
        fields = ["action", "note"]
