from django import forms

from apps.tenant.academics.models import CourseOffering

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
        help_texts = {
            "weight": "Optional. Use when combining multiple assessments into a weighted final result. Example: 30 for coursework or 70 for exam.",
            "is_published": "Only published assessments are visible to students and parents.",
        }

    def __init__(self, *args, **kwargs):
        offerings = kwargs.pop("offerings", None)
        super().__init__(*args, **kwargs)
        self.fields["offering"].queryset = offerings if offerings is not None else CourseOffering.objects.all()

    def clean_max_score(self):
        value = self.cleaned_data.get("max_score")
        if value is not None and value <= 0:
            raise forms.ValidationError("Maximum score must be greater than zero.")
        return value

    def clean_weight(self):
        value = self.cleaned_data.get("weight")
        if value is not None and value < 0:
            raise forms.ValidationError("Weight cannot be negative.")
        return value
