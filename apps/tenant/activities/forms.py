from django import forms

from apps.tenant.hr.models import StaffProfile
from apps.tenant.orgsettings.models import Campus

from .models import Activity


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = [
            "name",
            "type",
            "description",
            "campus",
            "head",
            "meeting_day",
            "meeting_time",
            "location",
            "poster",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        campuses = kwargs.pop("campuses", None)
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)
        self.fields["campus"].queryset = campuses if campuses is not None else Campus.objects.all()
        head_qs = StaffProfile.objects.select_related("campus").filter(is_active=True)
        if campus_scope:
            head_qs = head_qs.filter(campus=campus_scope)
        self.fields["head"].queryset = head_qs
