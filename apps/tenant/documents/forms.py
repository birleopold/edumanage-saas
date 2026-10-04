from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Document


def validate_school_document(upload):
    max_bytes = getattr(settings, "DOCUMENT_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
    allowed_extensions = set(
        getattr(
            settings,
            "DOCUMENT_UPLOAD_ALLOWED_EXTENSIONS",
            (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".jpg", ".jpeg", ".png", ".webp"),
        )
    )
    extension = Path(upload.name or "").suffix.lower()
    if extension not in allowed_extensions:
        raise ValidationError("This file type is not allowed.")
    if upload.size > max_bytes:
        raise ValidationError(f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.")
    return upload


class DocumentCreateForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "description", "file", "audience", "is_active"]

    def clean_file(self):
        return validate_school_document(self.cleaned_data["file"])


class DocumentEditForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "description", "audience", "is_active"]
