from django import forms

from apps.tenant.academics.models import AcademicTerm
from apps.tenant.students.models import StudentProfile

from .models import DocumentTemplate


def clean_design_background(upload):
    if upload is None:
        return None
    if upload.size > 12 * 1024 * 1024:
        raise forms.ValidationError("Design background artwork must be 12 MB or smaller.")
    image = forms.ImageField().clean(upload)
    content_type = (getattr(image, "content_type", "") or "").lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise forms.ValidationError("Use a JPG, PNG or WebP image for design background artwork.")
    return image


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ["name", "document_type", "description", "campus", "stage", "level", "is_default", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
        for name in ("is_default", "is_active"):
            self.fields[name].widget.attrs["class"] = "h-5 w-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
        if campus:
            self.fields["campus"].queryset = self.fields["campus"].queryset.filter(pk=campus.pk)
            self.fields["campus"].initial = campus
            self.fields["campus"].required = True
        if self.instance and self.instance.pk:
            # Changing a document family after versions exist would make its history ambiguous.
            self.fields["document_type"].disabled = True


class DocumentGenerationForm(forms.Form):
    student = forms.ModelChoiceField(queryset=StudentProfile.objects.none())
    academic_term = forms.ModelChoiceField(queryset=AcademicTerm.objects.all().select_related("year"), required=False)

    def __init__(self, *args, campus=None, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        students = StudentProfile.objects.filter(is_active=True).select_related("campus", "stream__class_group")
        if campus:
            students = students.filter(campus=campus)
        if template is not None:
            if template.campus_id:
                students = students.filter(campus_id=template.campus_id)
            if template.level_id:
                students = students.filter(stream__class_group__level_id=template.level_id)
        self.fields["student"].queryset = students
        for field in self.fields.values():
            field.widget.attrs["class"] = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
