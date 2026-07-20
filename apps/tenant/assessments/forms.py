from django import forms

from apps.tenant.academics.models import CourseOffering

from .models import (
    Assessment,
    AssessmentType,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
    normalize_assessment_code,
)
from .services import scheme_validation_errors


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            "offering",
            "name",
            "assessment_type",
            "weighting_component",
            "max_score",
            "weight",
            "date",
            "is_published",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }
        help_texts = {
            "assessment_type": "Optional classification used by the configurable weighting framework.",
            "weighting_component": "Optional explicit scheme component. Leave blank to resolve by assessment type.",
            "weight": "Legacy weight remains supported when no weighting scheme applies.",
            "is_published": "Only published assessments are visible to students and parents.",
        }

    def __init__(self, *args, **kwargs):
        offerings = kwargs.pop("offerings", None)
        super().__init__(*args, **kwargs)
        self.fields["offering"].queryset = offerings if offerings is not None else CourseOffering.objects.all()
        self.fields["assessment_type"].queryset = AssessmentType.objects.filter(is_active=True).order_by("kind", "name")
        components = AssessmentWeightingComponent.objects.filter(
            is_active=True,
            scheme__is_active=True,
            assessment_type__is_active=True,
        ).select_related("scheme", "assessment_type")
        selected_type = None
        if self.is_bound:
            selected_type = self.data.get("assessment_type")
        elif self.instance and self.instance.assessment_type_id:
            selected_type = self.instance.assessment_type_id
        if selected_type:
            components = components.filter(assessment_type_id=selected_type)
        self.fields["weighting_component"].queryset = components.order_by("scheme__name", "order")

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

    def clean(self):
        cleaned = super().clean()
        assessment_type = cleaned.get("assessment_type")
        component = cleaned.get("weighting_component")
        if component and assessment_type and component.assessment_type_id != assessment_type.pk:
            self.add_error("weighting_component", "The component must use the selected assessment type.")
        if component and (not component.is_active or not component.scheme.is_active):
            self.add_error("weighting_component", "Choose a component from an active scheme.")
        return cleaned


class AssessmentTypeForm(forms.ModelForm):
    class Meta:
        model = AssessmentType
        fields = [
            "code",
            "name",
            "kind",
            "description",
            "default_max_score",
            "default_weight",
            "local_aliases",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "local_aliases": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "local_aliases": 'Optional JSON aliases, for example {"UG": "EOT"}.',
        }

    def clean_code(self):
        return normalize_assessment_code(self.cleaned_data.get("code"))


class AssessmentWeightingSchemeForm(forms.ModelForm):
    class Meta:
        model = AssessmentWeightingScheme
        fields = [
            "code",
            "name",
            "description",
            "campus",
            "stage",
            "academic_term",
            "program",
+            "total_weight",
            "missing_score_policy",
            "normalize_to_total",
            "priority",
            "is_default",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "priority": "Higher priority wins when more than one valid scheme matches an offering.",
            "is_default": "Used as a tie-breaker after scope specificity and priority.",
        }

    def clean_code(self):
        return normalize_assessment_code(self.cleaned_data.get("code"))

    def clean(self):
        cleaned = super().clean()
        scope_fields = ("campus", "stage", "academic_term", "program")
        if all(field in cleaned for field in scope_fields) and "priority" in cleaned:
            duplicate = AssessmentWeightingScheme.objects.filter(
                campus=cleaned.get("campus"),
                stage=cleaned.get("stage"),
                academic_term=cleaned.get("academic_term"),
                program=cleaned.get("program"),
                priority=cleaned.get("priority"),
                is_active=True,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if cleaned.get("is_active") and duplicate.exists():
                raise forms.ValidationError(
                    "Another active scheme has the same scope and priority. Change the priority or narrow the scope."
                )
        return cleaned


class AssessmentWeightingComponentForm(forms.ModelForm):
    class Meta:
        model = AssessmentWeightingComponent
        fields = [
            "assessment_type",
            "weight",
            "aggregation_method",
            "minimum_occurrences",
            "maximum_occurrences",
            "drop_lowest_count",
            "is_required",
            "is_active",
            "order",
        ]

    def __init__(self, *args, **kwargs):
        self.scheme = kwargs.pop("scheme", None)
        super().__init__(*args, **kwargs)
        types = AssessmentType.objects.filter(is_active=True)
        if self.scheme:
            used_ids = self.scheme.components.exclude(pk=self.instance.pk).values_list("assessment_type_id", flat=True)
            types = types.exclude(pk__in=used_ids)
        self.fields["assessment_type"].queryset = types.order_by("kind", "name")

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.scheme:
            obj.scheme = self.scheme
        if commit:
            obj.full_clean()
            obj.save()
        return obj


class SchemeActivationForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label="I confirm this scheme is ready for use",
    )

    def __init__(self, *args, scheme=None, **kwargs):
        self.scheme = scheme
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        if self.scheme:
            errors = scheme_validation_errors(self.scheme)
            if errors:
                raise forms.ValidationError(errors)
        return cleaned
