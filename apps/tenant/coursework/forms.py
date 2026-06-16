from django import forms

from .models import Assignment, LearningMaterial


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class LearningMaterialForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text="Optional: attach notes, PDFs, images, videos, or other learning files.",
    )

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
            "attachments",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "publish_at": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class AssignmentForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text="Optional: attach question papers, rubrics, templates, or reference files.",
    )

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
            "attachments",
        ]
        widgets = {
            "publish_at": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local", "placeholder": "YYYY-MM-DD HH:MM"}),
            "instructions": forms.Textarea(attrs={"rows": 5}),
        }

    def clean(self):
        cleaned = super().clean()
        max_score = cleaned.get("max_score")
        if max_score is not None and max_score <= 0:
            self.add_error("max_score", "Maximum score must be greater than zero.")
        publish_at = cleaned.get("publish_at")
        due_date = cleaned.get("due_date")
        if publish_at and due_date and due_date < publish_at:
            self.add_error("due_date", "Due date cannot be earlier than the publish date.")
        return cleaned
