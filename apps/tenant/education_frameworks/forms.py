from django import forms

from apps.tenant.academics.models import GradingScale
from apps.tenant.orgsettings.models import Campus

from .models import (
    AcademicFramework,
    CampusEducationStage,
    EducationStage,
    FrameworkStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from .services import MAPPING_SOURCE_MANUAL


TERMINOLOGY_FIELDS = (
    ("institution", "Institution"),
    ("learner", "Learner"),
    ("guardian", "Parent or guardian"),
    ("teacher", "Teacher"),
    ("class", "Class or year"),
    ("stream", "Stream or section"),
    ("subject", "Subject"),
    ("course", "Course"),
    ("course_unit", "Course unit"),
    ("academic_period", "Academic period"),
    ("term", "Term"),
    ("semester", "Semester"),
    ("assessment", "Assessment"),
    ("exam", "Exam"),
    ("coursework", "Coursework"),
    ("assignment", "Assignment"),
    ("report_card", "Report card"),
    ("candidate", "Candidate"),
    ("external_exam", "External exam"),
    ("boarding", "Boarding and welfare"),
    ("hostel", "Hostel or residence"),
    ("house", "House"),
    ("fees", "Fees"),
    ("clearance", "Clearance"),
    ("activities", "Clubs, sports and activities"),
)


class InstitutionEducationProfileForm(forms.ModelForm):
    class Meta:
        model = InstitutionEducationProfile
        fields = [
            "institution_type",
            "country_code",
            "locale",
            "primary_framework",
            "use_local_terminology",
            "is_active",
        ]
        help_texts = {
            "country_code": "Two-letter country code, for example UG, KE, TZ or GB.",
            "locale": "Language and regional format, for example en-UG or en-GB.",
            "primary_framework": "This provides defaults only. School-specific settings remain editable.",
            "use_local_terminology": "Use framework labels such as O-Level, A-Level, UNEB and MDD where applicable.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["primary_framework"].queryset = AcademicFramework.objects.filter(
            is_active=True
        ).order_by("country_code", "name")

    def clean_country_code(self):
        value = (self.cleaned_data.get("country_code") or "").strip().upper()
        if len(value) != 2 or not value.isalpha():
            raise forms.ValidationError("Enter a valid two-letter country code.")
        return value

    def clean_locale(self):
        value = (self.cleaned_data.get("locale") or "").strip()
        if not value:
            raise forms.ValidationError("Enter a locale such as en-UG.")
        return value


class TerminologyOverridesForm(forms.Form):
    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        overrides = dict(getattr(profile, "terminology", {}) or {})
        for key, label in TERMINOLOGY_FIELDS:
            self.fields[key] = forms.CharField(
                label=label,
                required=False,
                max_length=96,
                initial=overrides.get(key, ""),
                help_text="Leave blank to use the framework default.",
            )

    def save(self):
        if self.profile is None:
            raise ValueError("A profile is required to save terminology overrides.")
        self.profile.terminology = {
            key: value.strip()
            for key, value in self.cleaned_data.items()
            if isinstance(value, str) and value.strip()
        }
        self.profile.save(update_fields=["terminology", "updated_at"])
        return self.profile


class CampusEducationStageForm(forms.ModelForm):
    grading_scale = forms.ModelChoiceField(
        queryset=GradingScale.objects.none(),
        required=False,
        help_text="Optional existing grading scale used by this stage.",
    )

    class Meta:
        model = CampusEducationStage
        fields = [
            "campus",
            "stage",
            "local_name",
            "academic_period_type",
            "grading_scale",
            "default_assessment_mode",
            "report_mode",
            "report_layout_key",
            "candidate_class",
            "supports_promotion_decisions",
            "is_active",
        ]
        help_texts = {
            "local_name": "Optional local label, for example O-Level, A-Level, Lower Primary or TVET.",
            "default_assessment_mode": "Choose the default interpretation for marks and competency records in this stage.",
            "report_mode": "Choose the normal report presentation used by this stage.",
            "report_layout_key": "Required only for a custom report mode. Leave blank for standard templates.",
            "candidate_class": "Enable candidate registration and external-examination readiness for this stage.",
            "supports_promotion_decisions": "Allow configured result policies to produce progression or promotion decisions.",
        }

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.fields["campus"].queryset = Campus.objects.filter(
            organization=profile.organization,
            is_active=True,
        ).order_by("name")
        self.fields["stage"].queryset = EducationStage.objects.filter(
            is_active=True
        ).order_by("order", "name")
        self.fields["grading_scale"].queryset = GradingScale.objects.filter(
            is_active=True
        ).order_by("-is_default", "name")
        if self.instance and self.instance.pk and self.instance.grading_scale_id:
            self.fields["grading_scale"].initial = self.instance.grading_scale_id

    def clean(self):
        cleaned = super().clean()
        campus = cleaned.get("campus")
        stage = cleaned.get("stage")
        report_mode = cleaned.get("report_mode")
        report_layout_key = (cleaned.get("report_layout_key") or "").strip()
        if campus and campus.organization_id != self.profile.organization_id:
            self.add_error("campus", "Select a campus belonging to this institution.")
        if campus and stage:
            duplicate = CampusEducationStage.objects.filter(
                profile=self.profile,
                campus=campus,
                stage=stage,
            ).exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    "stage",
                    "This education stage is already configured for the selected campus.",
                )
        if stage and self.profile.primary_framework_id:
            framework_stage = FrameworkStage.objects.filter(
                framework=self.profile.primary_framework,
                stage=stage,
                is_active=True,
            ).first()
            if framework_stage is None:
                self.add_error(
                    "stage",
                    "The selected curriculum framework does not currently support this education stage.",
                )
            cleaned["framework_stage"] = framework_stage
        if report_mode == CampusEducationStage.REPORT_CUSTOM and not report_layout_key:
            self.add_error(
                "report_layout_key",
                "Enter a report layout key when the custom report mode is selected.",
            )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.profile = self.profile
        instance.framework_stage = self.cleaned_data.get("framework_stage")
        grading_scale = self.cleaned_data.get("grading_scale")
        instance.grading_scale = grading_scale
        instance.legacy_grading_scale_id = grading_scale.pk if grading_scale else None
        instance.grading_scale_name = grading_scale.name if grading_scale else ""
        if not instance.local_name and instance.framework_stage_id:
            instance.local_name = instance.framework_stage.local_name
        if commit:
            instance.full_clean()
            instance.save()
        return instance


class LevelStageMappingForm(forms.ModelForm):
    class Meta:
        model = LevelStageMapping
        fields = ["stage", "local_name"]
        help_texts = {
            "stage": "Correct the automatic classification without changing the existing academic level.",
            "local_name": "Optional display label. The original level name remains unchanged.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stage"].queryset = EducationStage.objects.filter(
            is_active=True
        ).order_by("order", "name")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.settings = {
            **dict(instance.settings or {}),
            "source": MAPPING_SOURCE_MANUAL,
        }
        if commit:
            instance.full_clean()
            instance.save()
        return instance
