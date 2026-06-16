from django import forms

from apps.tenant.academics.models import CourseOffering

from .models import Period, Room, TimetableEntry
from .services import clash_messages_for_form


class PeriodForm(forms.ModelForm):
    class Meta:
        model = Period
        fields = ["name", "order", "start_time", "end_time", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time", "placeholder": "HH:MM"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "placeholder": "HH:MM"}),
        }

    def clean(self):
        cleaned = super().clean()
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError("Period start time must be before end time.")
        return cleaned


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "code", "capacity", "is_active"]

    def clean_capacity(self):
        value = self.cleaned_data.get("capacity")
        if value is not None and value <= 0:
            raise forms.ValidationError("Room capacity must be greater than zero.")
        return value


class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ["offering", "weekday", "period", "room", "note", "is_active"]
        help_texts = {
            "offering": "Select the course offering to schedule.",
            "period": "The system checks this slot for teacher, class, room, and student clashes.",
            "room": "Optional, but room clashes are checked when a room is selected.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["offering"].queryset = CourseOffering.objects.select_related(
            "course", "term", "term__year", "class_group", "teacher", "campus"
        ).filter(is_active=True)
        self.fields["period"].queryset = Period.objects.filter(is_active=True)
        self.fields["room"].queryset = Room.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        offering = cleaned.get("offering")
        weekday = cleaned.get("weekday")
        period = cleaned.get("period")
        room = cleaned.get("room")
        is_active = cleaned.get("is_active")
        exclude_entry_id = self.instance.pk if self.instance and self.instance.pk else None

        clashes = clash_messages_for_form(
            offering=offering,
            weekday=weekday,
            period=period,
            room=room,
            exclude_entry_id=exclude_entry_id,
            is_active=is_active,
        )
        if clashes:
            raise forms.ValidationError(clashes)
        return cleaned
