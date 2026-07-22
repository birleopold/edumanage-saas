import json

from django import forms

from .models import (
    CandidateDossier,
    CandidateExamAttendance,
    CandidateMockCycle,
    ECDObservation,
    LearnerSubjectCombination,
    MealAttendance,
    MealService,
    ReportTemplate,
    ResultPolicy,
    StudentProperty,
    VerifiablePermit,
    VisitationWindow,
    VisitorRecord,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " w-full rounded-xl border border-slate-300 px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-200").strip()
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "h-5 w-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500"


class ReportTemplateForm(StyledModelForm):
    sections_text = forms.CharField(
        required=False,
        help_text="Enter section keys in display order, separated by commas: identity, results, attendance, ecd, activities, finance, comments, signatures.",
    )

    class Meta:
        model = ReportTemplate
        exclude = ("sections", "created_at", "updated_at")
        widgets = {"settings": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["sections_text"].initial = ", ".join(self.instance.sections or [])

    def clean_sections_text(self):
        return [item.strip().lower() for item in self.cleaned_data.get("sections_text", "").split(",") if item.strip()]

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.sections = self.cleaned_data["sections_text"] or ["identity", "results", "attendance", "comments", "signatures"]
        obj.full_clean()
        if commit:
            obj.save()
        return obj


class ResultPolicyForm(StyledModelForm):
    class Meta:
        model = ResultPolicy
        exclude = ("created_at", "updated_at")
        widgets = {"settings": forms.Textarea(attrs={"rows": 7})}


class ECDObservationForm(StyledModelForm):
    class Meta:
        model = ECDObservation
        exclude = ("recorded_by", "updated_at")
        widgets = {"observation": forms.Textarea(attrs={"rows": 3}), "recommendation": forms.Textarea(attrs={"rows": 3})}


class LearnerSubjectCombinationForm(StyledModelForm):
    class Meta:
        model = LearnerSubjectCombination
        exclude = ("registered_by",)


class CandidateDossierForm(StyledModelForm):
    checklist_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="One required document per line. Prefix completed items with [x], for example: [x] Birth certificate.",
    )

    class Meta:
        model = CandidateDossier
        exclude = ("checklist", "verification_token", "verified_by", "verified_at", "created_at", "updated_at")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            lines = []
            for label, complete in (self.instance.checklist or {}).items():
                lines.append(f"[{'x' if complete else ' '}] {label}")
            self.fields["checklist_text"].initial = "\n".join(lines)

    def clean_checklist_text(self):
        checklist = {}
        for raw in self.cleaned_data.get("checklist_text", "").splitlines():
            line = raw.strip()
            if not line:
                continue
            complete = line.lower().startswith("[x]")
            label = line[3:].strip() if line.startswith("[") and "]" in line[:4] else line
            if label:
                checklist[label] = complete
        return checklist

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.checklist = self.cleaned_data["checklist_text"]
        obj.full_clean()
        if commit:
            obj.save()
        return obj


class CandidateMockCycleForm(StyledModelForm):
    class Meta:
        model = CandidateMockCycle
        fields = "__all__"


class CandidateExamAttendanceForm(StyledModelForm):
    class Meta:
        model = CandidateExamAttendance
        exclude = ("marked_by", "marked_at")


class PermitForm(StyledModelForm):
    class Meta:
        model = VerifiablePermit
        exclude = ("verification_token", "approved_by", "issued_at", "used_at")
        widgets = {"metadata": forms.Textarea(attrs={"rows": 6})}


class VisitationWindowForm(StyledModelForm):
    class Meta:
        model = VisitationWindow
        fields = "__all__"
        widgets = {"instructions": forms.Textarea(attrs={"rows": 4})}


class VisitorRecordForm(StyledModelForm):
    class Meta:
        model = VisitorRecord
        exclude = ("verified_by",)
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}


class MealServiceForm(StyledModelForm):
    class Meta:
        model = MealService
        exclude = ("recorded_by",)


class MealAttendanceForm(StyledModelForm):
    class Meta:
        model = MealAttendance
        exclude = ("marked_by",)


class StudentPropertyForm(StyledModelForm):
    class Meta:
        model = StudentProperty
        exclude = ("received_by",)
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}
