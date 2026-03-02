from django import forms

from .models import Bed, BedAllocation, Hostel, HostelRoom


class HostelForm(forms.ModelForm):
    class Meta:
        model = Hostel
        fields = ["name", "code", "is_active"]


class HostelRoomForm(forms.ModelForm):
    class Meta:
        model = HostelRoom
        fields = ["hostel", "name", "code", "capacity", "is_active"]


class BedForm(forms.ModelForm):
    class Meta:
        model = Bed
        fields = ["room", "label", "is_active"]


class BedAllocationForm(forms.ModelForm):
    class Meta:
        model = BedAllocation
        fields = ["bed", "student", "start_date", "end_date", "status", "note"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def clean(self):
        cleaned = super().clean()
        bed = cleaned.get("bed")
        status = cleaned.get("status")

        if bed and status == BedAllocation.ACTIVE:
            qs = BedAllocation.objects.filter(bed=bed, status=BedAllocation.ACTIVE)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("bed", "This bed already has an active allocation.")

        return cleaned
