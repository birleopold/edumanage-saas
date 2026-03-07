from django import forms

from .models import Assignment, LearningMaterial


class LearningMaterialForm(forms.ModelForm):
    class Meta:
        model = LearningMaterial
        fields = [
            "type",
            "title",
            "description",
            "campus",
            "class_group",
            "stream",
            "offering",
            "publish_at",
            "due_date",
            "is_active",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "publish_at": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
        }


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = [
            "title",
            "instructions",
            "max_score",
            "campus",
            "class_group",
            "stream",
            "offering",
            "publish_at",
            "due_date",
            "is_active",
        ]
        widgets = {
            "publish_at": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
        }
