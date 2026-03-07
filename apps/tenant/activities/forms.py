from django import forms

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
