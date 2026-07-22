from django import forms

from apps.tenant.academics.models import CourseOffering
from apps.tenant.teachers.models import TeacherProfile

from .models import (
    Assessment,
    AssessmentType,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
    normalize_assessment_code,
)
from .policy_models import AssessmentPolicy
from .services import scheme_validation_errors


class AssessmentForm(forms.ModelForm):
    grading_mode = forms.ChoiceField(
        choices=AssessmentPolicy.GRADING_MODE_CHOICES,
        initial=AssessmentPolicy.NUMERIC,
    )
    absence_policy = forms.ChoiceField(
        choices=AssessmentPolicy.ABSENCE_POLICY_CHOICES,
        initial=AssessmentPolicy.MISSING,
    )
    show_on_report = forms.BooleanField(required=False, initial=True)
    allow_makeup = forms.BooleanField(required=False)
    responsible_teacher = forms.ModelChoiceField(
        queryset=TeacherProfile.objects.none(),
        required=False,
    )
    competency_framework_key = forms.CharField(
        required=False,
        max_length=96,
    )
    makeup_for = forms.ModelChoiceField(
        queryset=Assessment.objects.none(),
        required=False,
    )
    deferred_until = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

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
            "grading_mode",
            "absence_policy",
            "show_on_report",
            "allow_makeup",
            "responsible_teacher",
            "competency_framework_key",
            "makeup_for",
            "deferred_until",
            "is_published",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }
        help_texts = {
            "assessment_type": "Optional classification used by the configurable weighting framework.",
            "weighting_component": "Optional explicit scheme component. Leave blank to resolve by assessment type.",
            "weight": "Legacy weight remains supported when no weighting scheme applies.",
            "grading_mode": "Choose numeric, competency, or mixed result interpretation.",
            "absence_policy": "Controls how an absent learner affects the result.",
            "show_on_report": "Include this published assessment in report-card and transcript calculations.",
            "allow_makeup": "Allow a later assessment to replace a deferred or missed attempt.",
            "competency_framework_key": "Optional competency framework or rubric identifier.",
            "makeup_for": "Optional original assessment replaced by this makeup assessment.",
            "is_published": "Only published assessments are visible to students and parents.",
        }

    def __init__(self, *args, **kwargs):
        offerings = kwargs.pop("offerings", None)
        super().__init__(*args, **kwargs)
        self.fields["offering"].queryset = (
            offerings if offerings is not None else CourseOffering.objects.all()
        )
        self.fields["assessment_type"].queryset = AssessmentType.objects.filter(
            is_active=True
        ).order_by("kind", "name")
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
        self.fields["weighting_component"].queryset = components.order_by(
            "scheme__name",
            "order",
        )

        selected_offering = None
        if self.is_bound:
            selected_offering = self.data.get("offering")
        elif self.instance and self.instance.offering_id:
            selected_offering = self.instance.offering_id
        teachers = TeacherProfile.objects.all().order_by("last_name", "first_name")
        makeup_assessments = Assessment.objects.all().select_related(
            "offering",
            "offering__course",
        )
        if selected_offering:
            teachers = teachers.filter(
                campus_id__in=CourseOffering.objects.filter(pk=selected_offering).values_list(
                    "campus_id",
                    flat=True,
                )
            ) | teachers.filter(campus__isnull=True)
            makeup_assessments = makeup_assessments.filter(offering_id=selected_offering)
        if self.instance and self.instance.pk:
            makeup_assessments = makeup_assessments.exclude(pk=self.instance.pk)
        self.fields["responsible_teacher"].queryset = teachers.distinct()
        self.fields["makeup_for"].queryset = makeup_assessments.order_by(
            "-created_at",
            "name",
        )

        policy = None
        if self.instance and self.instance.pk:
            try:
                policy = self.instance.policy
            except AssessmentPolicy.DoesNotExist:
                policy = None
        if policy:
            for field_name in (
                "grading_mode",
                "absence_policy",
                "show_on_report",
                "allow_makeup",
                "responsible_teacher",
                "competency_framework_key",
                "makeup_for",
                "deferred_until",
            ):
                self.fields[field_name].initial = getattr(policy, field_name)
        elif self.instance and self.instance.offering_id:
            self.fields["responsible_teacher"].initial = self.instance.offering.teacher_id

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
        absence_policy = cleaned.get("absence_policy")
        allow_makeup = bool(cleaned.get("allow_makeup"))
        makeup_for = cleaned.get("makeup_for")
        offering = cleaned.get("offering")
        if component and assessment_type and component.assessment_type_id != assessment_type.pk:
            self.add_error(
                "weighting_component",
                "The component must use the selected assessment type.",
            )
        if component and (not component.is_active or not component.scheme.is_active):
            self.add_error(
                "weighting_component",
                "Choose a component from an active scheme.",
            )
        if absence_policy in {
            AssessmentPolicy.DEFERRED,
            AssessmentPolicy.MAKEUP_REQUIRED,
        } and not allow_makeup:
            self.add_error(
                "allow_makeup",
                "Deferred or makeup-required absence policies must allow a makeup assessment.",
            )
        if makeup_for and offering and makeup_for.offering_id != offering.pk:
            self.add_error(
                "makeup_for",
                "The original and makeup assessments must use the same course offering.",
            )
        return cleaned

    def save(self, commit=True):
        assessment = super().save(commit=commit)
        if not commit:
            return assessment
        policy, _ = AssessmentPolicy.objects.update_or_create(
            assessment=assessment,
            defaults={
                "grading_mode": self.cleaned_data["grading_mode"],
                "absence_policy": self.cleaned_data["absence_policy"],
                "show_on_report": bool(self.cleaned_data.get("show_on_report")),
                "allow_makeup": bool(self.cleaned_data.get("allow_makeup")),
                "responsible_teacher": self.cleaned_data.get("responsible_teacher"),
                "competency_framework_key": self.cleaned_data.get(
                    "competency_framework_key",
                    "",
                ),
                "makeup_for": self.cleaned_data.get("makeup_for"),
                "deferred_until": self.cleaned_data.get("deferred_until"),
            },
        )
        policy.full_clean()
        policy.save()
        return assessment


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
            "total_weight",
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
            used_ids = self.scheme.components.exclude(pk=self.instance.pk).values_list(
                "assessment_type_id",
                flat=True,
            )
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
