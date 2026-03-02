from django import forms

from .models import Document


class DocumentCreateForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "description", "file", "audience", "is_active"]


class DocumentEditForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "description", "audience", "is_active"]
