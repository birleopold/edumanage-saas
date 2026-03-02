from django import forms

from .models import Period, Room, TimetableEntry


class PeriodForm(forms.ModelForm):
    class Meta:
        model = Period
        fields = ["name", "order", "start_time", "end_time", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time", "placeholder": "HH:MM"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "placeholder": "HH:MM"}),
        }


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "code", "capacity", "is_active"]


class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ["offering", "weekday", "period", "room", "note", "is_active"]
