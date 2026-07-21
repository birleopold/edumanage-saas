from django import forms

from apps.tenant.assessments.models import AssessmentType, AssessmentWeightingComponent

from .models import LearningActivity


class LearningActivityPolicyForm(forms.ModelForm):
    class Meta:
        model = LearningActivity
        fields = [
            "kind",
            "position",
            "estimated_minutes",
            "completion_policy",
            "submission_policy",
            "assessment_type",
            "weighting_component",
            "local_aliases",
            "settings",
            "is_active",
        ]
        widgets = {
            "local_aliases": forms.Textarea(attrs={"rows": 4}),
            "settings": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "position": "Lower numbers appear first in unified activity views.",
            "local_aliases": 'Optional JSON aliases, for example {"UG": "Holiday work", "default": "Learning activity"}.',
            "settings": "Optional JSON for future activity-specific configuration.",
            "assessment_type": "Optional Phase 2 assessment classification.",
            "weighting_component": "Optional Phase 2 weighting component used when this activity contributes to results.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assessment_type"].queryset = AssessmentType.objects.filter(is_active=True).order_by("kind", "name")
        self.fields["weighting_component"].queryset = AssessmentWeightingComponent.objects.filter(
            is_active=True,
            scheme__is_active=True,
        ).select_related("scheme", "assessment_type").order_by("scheme__name", "order", "pk")

    def clean(self):
        cleaned = super().clean()
        assessment_type = cleaned.get("assessment_type")
        component = cleaned.get("weighting_component")
        submission_policy = cleaned.get("submission_policy")
        completion_policy = cleaned.get("completion_policy")
        if assessment_type and component and component.assessment_type_id != assessment_type.pk:
            self.add_error("weighting_component", "The weighting component must use the selected assessment type.")
        if completion_policy in {
            LearningActivity.COMPLETION_SUBMISSION,
            LearningActivity.COMPLETION_SCORE,
        } and submission_policy == LearningActivity.SUBMISSION_NONE:
            self.add_error("submission_policy", "Submission-based completion requires an optional or required submission policy.")
        return cleaned
