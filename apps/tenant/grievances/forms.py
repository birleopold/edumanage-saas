from django import forms

from .models import Grievance


class GrievanceSubmitForm(forms.ModelForm):
    class Meta:
        model = Grievance
        fields = ["subject", "body"]


class GrievanceAdminForm(forms.ModelForm):
    class Meta:
        model = Grievance
        fields = ["status", "resolution_notes"]
