from django import forms

from apps.tenant.hr.models import StaffProfile

from .models import ActivityMember
from .programme_models import (
    ActivityAchievement,
    ActivityGroup,
    ActivityParticipation,
    ActivityProgramme,
    ActivitySession,
)
from .programme_services import normalize_activity_code


class ActivityProgrammeForm(forms.ModelForm):
    class Meta:
        model = ActivityProgramme
        fields = [
            "code",
            "participation_mode",
            "capacity",
            "attendance_required",
            "guardian_consent_required",
            "medical_clearance_required",
            "competitive",
            "notes",
            "is_active",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_code(self):
        return normalize_activity_code(self.cleaned_data.get("code"))


class ActivityGroupForm(forms.ModelForm):
    class Meta:
        model = ActivityGroup
        fields = ["name", "group_type", "coach", "capacity", "notes", "is_active"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        programme = kwargs.pop("programme", None)
        super().__init__(*args, **kwargs)
        queryset = StaffProfile.objects.filter(is_active=True).select_related("campus")
        if programme and programme.activity.campus_id:
            queryset = queryset.filter(campus=programme.activity.campus)
        self.fields["coach"].queryset = queryset


class ActivityParticipationForm(forms.ModelForm):
    class Meta:
        model = ActivityParticipation
        fields = [
            "group",
            "role",
            "guardian_consent_status",
            "guardian_consent_recorded_at",
            "medical_clearance_status",
            "medical_clearance_recorded_at",
            "emergency_contact_name",
            "emergency_contact_phone",
            "notes",
        ]
        widgets = {
            "guardian_consent_recorded_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "medical_clearance_recorded_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        membership = kwargs.pop("membership", None)
        super().__init__(*args, **kwargs)
        if membership:
            self.fields["group"].queryset = ActivityGroup.objects.filter(
                programme__activity=membership.activity,
                is_active=True,
            )


class ActivitySessionForm(forms.ModelForm):
    class Meta:
        model = ActivitySession
        fields = [
            "activity",
            "group",
            "title",
            "session_type",
            "starts_at",
            "ends_at",
            "location",
            "attendance_required",
            "notes",
        ]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        activity_queryset = kwargs.pop("activity_queryset", None)
        super().__init__(*args, **kwargs)
        if activity_queryset is not None:
            self.fields["activity"].queryset = activity_queryset
        activity_id = self.data.get("activity") if self.is_bound else getattr(self.instance, "activity_id", None)
        if activity_id:
            self.fields["group"].queryset = ActivityGroup.objects.filter(
                programme__activity_id=activity_id,
                is_active=True,
            )
        else:
            self.fields["group"].queryset = ActivityGroup.objects.none()


class ActivityAchievementForm(forms.ModelForm):
    class Meta:
        model = ActivityAchievement
        fields = [
            "membership",
            "session",
            "title",
            "achievement_type",
            "level",
            "achieved_on",
            "position",
            "description",
        ]
        widgets = {
            "achieved_on": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        membership_queryset = kwargs.pop("membership_queryset", None)
        super().__init__(*args, **kwargs)
        if membership_queryset is not None:
            self.fields["membership"].queryset = membership_queryset
        membership_id = self.data.get("membership") if self.is_bound else getattr(self.instance, "membership_id", None)
        if membership_id:
            membership = ActivityMember.objects.filter(pk=membership_id).first()
            self.fields["session"].queryset = (
                ActivitySession.objects.filter(activity=membership.activity)
                if membership
                else ActivitySession.objects.none()
            )
        else:
            self.fields["session"].queryset = ActivitySession.objects.none()
