from django import forms

from .models import Assessment


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            "offering",
            "name",
            "max_score",
            "weight",
            "date",
            "is_published",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }
