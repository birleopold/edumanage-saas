from django import forms

from apps.tenant.discipline.models import Incident
from apps.tenant.sickbay.models import SickbayVisit
from apps.tenant.students.models import StudentProfile

from .models import (
    BedAllocation,
    BoardingLeave,
    BoardingProfile,
    Hostel,
    HostelRollCall,
    WelfareCase,
    WelfareCaseAction,
)


class BoardingProfileForm(forms.ModelForm):
    authorised_pickup_people_text = forms.CharField(
        required=False,
        label="Authorised pickup people",
        help_text="Enter one authorised person per line.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    class Meta:
        model = BoardingProfile
        fields = [
            "student",
            "boarding_status",
            "primary_guardian_name",
            "primary_guardian_phone",
            "alternate_contact_name",
            "alternate_contact_phone",
            "dietary_requirements",
            "accessibility_support",
            "safeguarding_note",
            "general_note",
            "is_active",
        ]
        widgets = {
            "dietary_requirements": forms.Textarea(attrs={"rows": 2}),
            "accessibility_support": forms.Textarea(attrs={"rows": 2}),
            "safeguarding_note": forms.Textarea(attrs={"rows": 3}),
            "general_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)
        students = StudentProfile.objects.filter(is_active=True).select_related("campus")
        if campus_scope:
            students = students.filter(campus=campus_scope)
        if self.instance and self.instance.pk:
            students = students.filter(pk=self.instance.student_id)
            self.fields["student"].disabled = True
            self.fields["authorised_pickup_people_text"].initial = "\n".join(
                str(item) for item in (self.instance.authorised_pickup_people or [])
            )
        else:
            students = students.exclude(boarding_profile__isnull=False)
        self.fields["student"].queryset = students.order_by("last_name", "first_name")

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.authorised_pickup_people = [
            line.strip()
            for line in (self.cleaned_data.get("authorised_pickup_people_text") or "").splitlines()
            if line.strip()
        ]
        if commit:
            obj.save()
        return obj


class BoardingLeaveForm(forms.ModelForm):
    class Meta:
        model = BoardingLeave
        fields = [
            "student",
            "bed_allocation",
            "linked_sickbay_visit",
            "leave_type",
            "expected_departure_at",
            "expected_return_at",
            "destination",
            "reason",
            "guardian_name",
            "guardian_phone",
            "handover_to",
        ]
        widgets = {
            "expected_departure_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "expected_return_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)
        students = StudentProfile.objects.filter(is_active=True).select_related("campus")
        if campus_scope:
            students = students.filter(campus=campus_scope)
        self.fields["student"].queryset = students.order_by("last_name", "first_name")
        student_id = self.data.get("student") if self.is_bound else getattr(self.instance, "student_id", None)
        allocations = BedAllocation.objects.none()
        visits = SickbayVisit.objects.none()
        if student_id:
            allocations = BedAllocation.objects.filter(student_id=student_id).select_related(
                "bed", "bed__room", "bed__room__hostel"
            )
            visits = SickbayVisit.objects.filter(student_id=student_id).order_by("-visit_at")
        self.fields["bed_allocation"].queryset = allocations
        self.fields["linked_sickbay_visit"].queryset = visits


class HostelRollCallForm(forms.ModelForm):
    class Meta:
        model = HostelRollCall
        fields = ["hostel", "roll_call_date", "shift", "taken_at", "notes"]
        widgets = {
            "roll_call_date": forms.DateInput(attrs={"type": "date"}),
            "taken_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hostel"].queryset = Hostel.objects.filter(is_active=True).order_by("name")


class WelfareCaseForm(forms.ModelForm):
    class Meta:
        model = WelfareCase
        fields = [
            "student",
            "category",
            "severity",
            "title",
            "summary",
            "confidential",
            "status",
            "assigned_to",
            "due_date",
            "linked_sickbay_visit",
            "linked_discipline_incident",
            "linked_bed_allocation",
            "resolution_summary",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "resolution_summary": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)
        students = StudentProfile.objects.filter(is_active=True).select_related("campus")
        if campus_scope:
            students = students.filter(campus=campus_scope)
        self.fields["student"].queryset = students.order_by("last_name", "first_name")
        student_id = self.data.get("student") if self.is_bound else getattr(self.instance, "student_id", None)
        if student_id:
            self.fields["linked_sickbay_visit"].queryset = SickbayVisit.objects.filter(
                student_id=student_id
            ).order_by("-visit_at")
            self.fields["linked_discipline_incident"].queryset = Incident.objects.filter(
                student_id=student_id
            ).order_by("-created_at")
            self.fields["linked_bed_allocation"].queryset = BedAllocation.objects.filter(
                student_id=student_id
            ).select_related("bed", "bed__room", "bed__room__hostel")
        else:
            self.fields["linked_sickbay_visit"].queryset = SickbayVisit.objects.none()
            self.fields["linked_discipline_incident"].queryset = Incident.objects.none()
            self.fields["linked_bed_allocation"].queryset = BedAllocation.objects.none()


class WelfareCaseActionForm(forms.ModelForm):
    class Meta:
        model = WelfareCaseAction
        fields = ["action_type", "note", "next_follow_up_at"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),
            "next_follow_up_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
