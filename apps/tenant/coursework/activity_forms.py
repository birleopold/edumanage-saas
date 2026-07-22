from django import forms

from apps.tenant.assessments.models import AssessmentType, AssessmentWeightingComponent

from .models import LearningActivity
from .workflow_models import LearningActivityProfile


class LearningActivityPolicyForm(forms.ModelForm):
    detailed_kind = forms.ChoiceField(
        choices=LearningActivityProfile.DETAILED_KIND_CHOICES,
        initial=LearningActivityProfile.OTHER,
    )
    group_work = forms.BooleanField(required=False)
    resubmission_allowed = forms.BooleanField(required=False)
    maximum_attempts = forms.IntegerField(min_value=1, initial=1)
    late_grace_minutes = forms.IntegerField(min_value=0, initial=0)
    competency_tracking = forms.BooleanField(required=False)
    competency_framework_key = forms.CharField(required=False, max_length=96)

    class Meta:
        model = LearningActivity
        fields = [
            "kind",
            "detailed_kind",
            "position",
            "estimated_minutes",
            "completion_policy",
            "submission_policy",
            "group_work",
            "resubmission_allowed",
            "maximum_attempts",
            "late_grace_minutes",
            "competency_tracking",
            "competency_framework_key",
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
            "detailed_kind": "Choose the exact academic activity type instead of relying on title inference.",
            "group_work": "Enable managed groups and one shared group submission.",
            "resubmission_allowed": "Allow returned work to be submitted again.",
            "maximum_attempts": "Maximum total attempts, including the first submission.",
            "late_grace_minutes": "Minutes after the deadline before a submission is classified as late.",
            "competency_tracking": "Require a competency rating when the activity is marked.",
            "competency_framework_key": "Rubric or competency framework identifier.",
            "local_aliases": 'Optional JSON aliases, for example {"UG": "Holiday work", "default": "Learning activity"}.',
            "settings": "Optional JSON for future activity-specific configuration.",
            "assessment_type": "Optional Phase 2 assessment classification.",
            "weighting_component": "Optional Phase 2 weighting component used when this activity contributes to results.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assessment_type"].queryset = AssessmentType.objects.filter(
            is_active=True
        ).order_by("kind", "name")
        self.fields["weighting_component"].queryset = (
            AssessmentWeightingComponent.objects.filter(
                is_active=True,
                scheme__is_active=True,
            )
            .select_related("scheme", "assessment_type")
            .order_by("scheme__name", "order", "pk")
        )
        profile = None
        if self.instance and self.instance.pk:
            try:
                profile = self.instance.workflow_profile
            except LearningActivityProfile.DoesNotExist:
                profile = None
        if profile:
            for field_name in (
                "detailed_kind",
                "group_work",
                "resubmission_allowed",
                "maximum_attempts",
                "late_grace_minutes",
                "competency_tracking",
                "competency_framework_key",
            ):
                self.fields[field_name].initial = getattr(profile, field_name)

    def clean(self):
        cleaned = super().clean()
        assessment_type = cleaned.get("assessment_type")
        component = cleaned.get("weighting_component")
        submission_policy = cleaned.get("submission_policy")
        completion_policy = cleaned.get("completion_policy")
        detailed_kind = cleaned.get("detailed_kind")
        group_work = bool(cleaned.get("group_work"))
        resubmission_allowed = bool(cleaned.get("resubmission_allowed"))
        maximum_attempts = cleaned.get("maximum_attempts") or 1
        competency_tracking = bool(cleaned.get("competency_tracking"))
        competency_framework_key = (
            cleaned.get("competency_framework_key") or ""
        ).strip()
        if assessment_type and component and component.assessment_type_id != assessment_type.pk:
            self.add_error(
                "weighting_component",
                "The weighting component must use the selected assessment type.",
            )
        if completion_policy in {
            LearningActivity.COMPLETION_SUBMISSION,
            LearningActivity.COMPLETION_SCORE,
        } and submission_policy == LearningActivity.SUBMISSION_NONE:
            self.add_error(
                "submission_policy",
                "Submission-based completion requires an optional or required submission policy.",
            )
        if detailed_kind == LearningActivityProfile.GROUP_ASSIGNMENT and not group_work:
            self.add_error("group_work", "Group assignments must enable group work.")
        if group_work and not self.instance.assignment_id:
            self.add_error("group_work", "Group work requires an assignment source.")
        if resubmission_allowed and maximum_attempts < 2:
            self.add_error(
                "maximum_attempts",
                "Allow at least two attempts when resubmission is enabled.",
            )
        if competency_tracking and not competency_framework_key:
            self.add_error(
                "competency_framework_key",
                "Enter a competency framework or rubric key.",
            )
        return cleaned

    def save(self, commit=True):
        activity = super().save(commit=commit)
        if not commit:
            return activity
        profile, _ = LearningActivityProfile.objects.update_or_create(
            activity=activity,
            defaults={
                "detailed_kind": self.cleaned_data["detailed_kind"],
                "group_work": bool(self.cleaned_data.get("group_work")),
                "resubmission_allowed": bool(
                    self.cleaned_data.get("resubmission_allowed")
                ),
                "maximum_attempts": self.cleaned_data.get("maximum_attempts") or 1,
                "late_grace_minutes": self.cleaned_data.get("late_grace_minutes") or 0,
                "competency_tracking": bool(
                    self.cleaned_data.get("competency_tracking")
                ),
                "competency_framework_key": self.cleaned_data.get(
                    "competency_framework_key",
                    "",
                ),
            },
        )
        profile.full_clean()
        profile.save()
        return activity
