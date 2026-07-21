from django import forms

from .grading_services import grading_profile_errors
from .models import GradingProfile, ReportRule, normalize_assessment_code


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
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "priority": "Higher priority wins when more than one valid profile matches.",
            "is_default": "Used as a tie-breaker after priority and scope specificity.",
            "promotion_percentage": "Leave blank to disable automatic promotion or progression status.",
            "minimum_passed_courses": "Optional minimum number of passed courses required for promotion.",
        }

    def clean_code(self):
        return normalize_assessment_code(self.cleaned_data.get("code"))

    def clean(self):
        cleaned = super().clean()
        if self.instance:
            for field, value in cleaned.items():
                if hasattr(self.instance, field):
                    setattr(self.instance, field, value)
            errors = grading_profile_errors(self.instance)
            if errors:
                raise forms.ValidationError(errors)
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
