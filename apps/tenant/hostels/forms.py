from django import forms

from apps.tenant.students.models import StudentProfile

from .models import Bed, BedAllocation, Hostel, HostelRoom


class HostelForm(forms.ModelForm):
    class Meta:
        model = Hostel
        fields = ["name", "code", "is_active"]


class HostelRoomForm(forms.ModelForm):
    class Meta:
        model = HostelRoom
        fields = ["hostel", "name", "code", "capacity", "is_active"]

    def clean_capacity(self):
        capacity = self.cleaned_data.get("capacity")
        if capacity is not None and capacity <= 0:
            raise forms.ValidationError("Room capacity must be greater than zero.")
        return capacity

    def clean(self):
        cleaned = super().clean()
        capacity = cleaned.get("capacity")
        if self.instance and self.instance.pk and capacity is not None:
            active_beds = self.instance.beds.filter(is_active=True).count()
            if capacity < active_beds:
                self.add_error("capacity", f"Capacity cannot be less than active beds already created ({active_beds}).")
        return cleaned


class BedForm(forms.ModelForm):
    class Meta:
        model = Bed
        fields = ["room", "label", "is_active"]

    def clean(self):
        cleaned = super().clean()
        room = cleaned.get("room")
        is_active = cleaned.get("is_active")
        if room and is_active:
            if not room.is_active:
                self.add_error("room", "Cannot create an active bed in an inactive room.")
            if room.capacity:
                active_beds = Bed.objects.filter(room=room, is_active=True)
                if self.instance and self.instance.pk:
                    active_beds = active_beds.exclude(pk=self.instance.pk)
                if active_beds.count() >= room.capacity:
                    self.add_error("room", "This room has reached its bed capacity.")
        return cleaned


class BedAllocationForm(forms.ModelForm):
    class Meta:
        model = BedAllocation
        fields = ["bed", "student", "start_date", "end_date", "status", "note"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = StudentProfile.objects.select_related("campus").all()
        if campus_scope:
            self.fields["student"].queryset = self.fields["student"].queryset.filter(campus=campus_scope)

    def clean(self):
        cleaned = super().clean()
        bed = cleaned.get("bed")
        student = cleaned.get("student")
        status = cleaned.get("status")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date cannot be before start date.")
        if status == BedAllocation.ACTIVE:
            if bed:
                if not bed.is_active or not bed.room.is_active or not bed.room.hostel.is_active:
                    self.add_error("bed", "Cannot allocate an inactive bed, room, or hostel.")
                bed_qs = BedAllocation.objects.filter(bed=bed, status=BedAllocation.ACTIVE)
                if self.instance and self.instance.pk:
                    bed_qs = bed_qs.exclude(pk=self.instance.pk)
                if bed_qs.exists():
                    self.add_error("bed", "This bed already has an active allocation.")
            if student:
                student_qs = BedAllocation.objects.filter(student=student, status=BedAllocation.ACTIVE)
                if self.instance and self.instance.pk:
                    student_qs = student_qs.exclude(pk=self.instance.pk)
                if student_qs.exists():
                    self.add_error("student", "This student already has an active hostel allocation.")
        return cleaned
