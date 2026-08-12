from django import forms
from django.db.models import Q

from apps.tenant.academics.models import AcademicTerm, Course, GradingScale, Level, Program
from apps.tenant.education_frameworks.models import (
    CampusEducationStage,
    EducationStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.orgsettings.models import Campus

from .grading_services import grading_scale_errors
from .models import GradingProfile, ReportRule, normalize_assessment_code


def _active_or_existing(queryset, existing_pk):
    if existing_pk:
        return queryset.model.objects.filter(Q(is_active=True) | Q(pk=existing_pk))
    return queryset.filter(is_active=True)


class GradingProfileForm(forms.ModelForm):
    class Meta:
        model = GradingProfile
        fields = [
            "code",
            "name",
            "description",
            "grading_scale",
            "campus",
            "stage",
            "level",
            "program",
            "course",
            "academic_term",
            "overall_aggregation",
            "incomplete_result_policy",
            "pass_percentage",
            "promotion_percentage",
            "minimum_passed_courses",
            "decimal_places",
            "priority",
            "is_default",
            "is_active",
        ]
        labels = {
            "code": "Rule code",
            "name": "Grading rule name",
            "grading_scale": "Grade scale",
            "campus": "Campus scope (optional)",
            "stage": "Education stage scope (optional)",
            "level": "Level scope (optional)",
            "program": "Programme scope (optional)",
            "course": "Subject / course scope (optional)",
            "academic_term": "Term / semester scope (optional)",
            "overall_aggregation": "How to calculate the overall result",
            "incomplete_result_policy": "What to do with incomplete subjects",
            "pass_percentage": "Pass percentage",
            "promotion_percentage": "Promotion / progression percentage (optional)",
            "minimum_passed_courses": "Minimum passed subjects/courses (optional)",
            "decimal_places": "Decimal places on calculated results",
            "priority": "Rule priority",
            "is_default": "Prefer this rule when equally specific rules match",
            "is_active": "This grading rule is in use",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "grading_scale": "The selected scale must be active and contain valid non-overlapping grade ranges.",
            "campus": "Leave blank when the rule should work across all campuses.",
            "stage": "Leave blank for a general rule. Choose a stage only when grading differs by Primary, O-Level, A-Level or another stage.",
            "level": "Leave blank unless this rule is specific to one level such as P7 or S4.",
            "program": "Mainly for programme-based or higher-education institutions. Leave blank otherwise.",
            "course": "Choose a subject/course only when this rule should override the broader grading rule for that subject.",
            "academic_term": "Leave blank when the same grading rule should continue across terms/semesters.",
            "priority": "Higher numbers win when more than one valid rule matches. Keep 0 unless the school intentionally uses overrides.",
            "is_default": "Used only as a tie-breaker after scope and priority. Most schools need one simple default rule.",
            "promotion_percentage": "Leave blank to disable automatic promotion/progression status.",
            "minimum_passed_courses": "Optional minimum number of passed subjects/courses required for promotion.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance if self.instance and self.instance.pk else None
        self.fields["grading_scale"].queryset = _active_or_existing(
            GradingScale.objects.all(),
            getattr(instance, "grading_scale_id", None),
        ).order_by("-is_default", "name")
        self.fields["campus"].queryset = _active_or_existing(
            Campus.objects.all(),
            getattr(instance, "campus_id", None),
        ).order_by("name")
        self.fields["stage"].queryset = _active_or_existing(
            EducationStage.objects.all(),
            getattr(instance, "stage_id", None),
        ).order_by("order", "name")
        self.fields["level"].queryset = _active_or_existing(
            Level.objects.all(),
            getattr(instance, "level_id", None),
        ).order_by("order", "name")
        self.fields["program"].queryset = _active_or_existing(
            Program.objects.all(),
            getattr(instance, "program_id", None),
        ).order_by("name")
        self.fields["course"].queryset = _active_or_existing(
            Course.objects.all(),
            getattr(instance, "course_id", None),
        ).order_by("name")
        self.fields["academic_term"].queryset = AcademicTerm.objects.select_related("year").order_by(
            "-is_current", "-year__name", "order"
        )

    def clean_code(self):
        return normalize_assessment_code(self.cleaned_data.get("code"))

    def clean(self):
        cleaned = super().clean()
        scale = cleaned.get("grading_scale")
        campus = cleaned.get("campus")
        stage = cleaned.get("stage")
        level = cleaned.get("level")
        program = cleaned.get("program")
        course = cleaned.get("course")
        if scale:
            errors = grading_scale_errors(scale)
            if errors:
                raise forms.ValidationError(errors)

        profile = InstitutionEducationProfile.objects.filter(is_active=True).first()
        mapping = None
        if profile and level:
            mapping = LevelStageMapping.objects.filter(
                profile=profile,
                legacy_level_id=level.pk,
            ).select_related("stage").first()
            if mapping is None:
                self.add_error(
                    "level",
                    "This level is not connected to an education stage. Return to School Setup and synchronize the education structure first.",
                )
            elif stage and mapping.stage_id != stage.pk:
                self.add_error(
                    "stage",
                    f"{level} is mapped to {mapping.stage}; choose that stage or leave the stage scope blank.",
                )

        if profile and campus and stage and not CampusEducationStage.objects.filter(
            profile=profile,
            campus=campus,
            stage=stage,
            is_active=True,
            stage__is_active=True,
        ).exists():
            self.add_error(
                "stage",
                f"{stage} is not enabled for {campus}. Review Education Structure before applying a grading rule to this campus/stage.",
            )

        if course and course.level_id and level and course.level_id != level.pk:
            self.add_error(
                "course",
                f"{course} is configured for {course.level}, not {level}. Change the scope or leave the level blank.",
            )
        if course and course.program_id and program and course.program_id != program.pk:
            self.add_error(
                "course",
                f"{course} belongs to {course.program}, not {program}. Change the programme scope or leave it blank.",
            )
        return cleaned


class ReportRuleForm(forms.ModelForm):
    class Meta:
        model = ReportRule
        fields = [
            "report_title",
            "result_label",
            "promotion_label",
            "show_percentage",
            "show_grade",
            "show_remark",
            "show_published_scores",
            "show_assessment_details",
            "show_component_breakdown",
            "show_promotion_status",
            "show_teacher_comments",
            "show_head_comments",
        ]
        labels = {
            "report_title": "Report title (optional)",
            "result_label": "Label for the final result",
            "promotion_label": "Label for promotion / progression",
            "show_percentage": "Show percentage",
            "show_grade": "Show grade",
            "show_remark": "Show grade remark",
            "show_published_scores": "Show published assessment scores",
            "show_assessment_details": "Show assessment details",
            "show_component_breakdown": "Show coursework/exam component breakdown",
            "show_promotion_status": "Show promotion / progression status",
            "show_teacher_comments": "Show teacher comments",
            "show_head_comments": "Show head teacher / administrator comments",
        }
        help_texts = {
            "report_title": "Leave blank to use the normal report-card title.",
            "show_promotion_status": "Turn this on only when the grading profile is configured to calculate progression/promotion.",
        }