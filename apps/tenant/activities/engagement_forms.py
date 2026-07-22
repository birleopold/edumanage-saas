from django import forms

from apps.tenant.students.models import StudentProfile

from .engagement_models import ActivityIncident
from .models import Activity
from .programme_models import ActivitySession


class ActivityIncidentForm(forms.ModelForm):
    class Meta:
        model = ActivityIncident
        fields = [
            "activity",
            "session",
            "student",
            "incident_type",
            "severity",
            "status",
            "occurred_at",
            "summary",
            "action_taken",
            "follow_up_at",
            "confidential",
            "resolved_at",
        ]
        widgets = {
            "occurred_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "follow_up_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "resolved_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "summary": forms.Textarea(attrs={"rows": 4}),
            "action_taken": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, campus=None, **kwargs):
        super().__init__(*args, **kwargs)
        activities = Activity.objects.filter(is_active=True)
        students = StudentProfile.objects.filter(is_active=True)
        sessions = ActivitySession.objects.all()
        if campus:
            activities = activities.filter(campus=campus)
            students = students.filter(campus=campus)
            sessions = sessions.filter(activity__campus=campus)
        activity_id = self.data.get("activity") if self.is_bound else getattr(self.instance, "activity_id", None)
        if activity_id:
            sessions = sessions.filter(activity_id=activity_id)
            students = students.filter(
                activity_memberships__activity_id=activity_id,
                activity_memberships__is_active=True,
            ).distinct()
        self.fields["activity"].queryset = activities.order_by("name")
        self.fields["session"].queryset = sessions.order_by("-starts_at")
        self.fields["student"].queryset = students.order_by("last_name", "first_name")
