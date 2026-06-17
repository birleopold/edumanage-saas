from django import forms

from .models import Assignment, CourseworkComment, LearningMaterial


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
            "external_url",
            "video_url",
            "meeting_url",
            "allow_comments",
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

    def clean(self):
        cleaned = super().clean()
        material_type = cleaned.get("type")
        video_url = cleaned.get("video_url")
        meeting_url = cleaned.get("meeting_url")
        if material_type == LearningMaterial.VIDEO_LESSON and not video_url:
            self.add_error("video_url", "Video lessons should include a video link or upload an attachment.")
        if material_type == LearningMaterial.LIVE_CLASS and not meeting_url:
            self.add_error("meeting_url", "Live classes should include a Google Meet, Zoom, or live-class link.")
        return cleaned


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
            "resource_url",
            "allow_comments",
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


class CourseworkCommentForm(forms.ModelForm):
    class Meta:
        model = CourseworkComment
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Ask a question or add a discussion comment..."})}

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if len(body) < 2:
            raise forms.ValidationError("Comment is too short.")
        return body
