from django import forms
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus

from .models import StudentProfile


class StudentProfileForm(forms.ModelForm):
    create_user = forms.BooleanField(
        required=False,
        initial=True,
        label="Create a learner portal login",
        help_text="Optional. Turn this off when the learner only needs a school record and will not sign in.",
    )
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        label="Email the login details",
        help_text="Only applies when a portal login is created and a usable email address is available.",
    )

    class Meta:
        model = StudentProfile
        fields = [
            "campus",
            "stream",
            "student_id",
            "email",
            "first_name",
            "last_name",
            "date_of_birth",
            "district",
            "subcounty",
            "parish",
            "nin",
            "learner_id",
            "is_active",
        ]
        labels = {
            "stream": "Class stream (optional)",
            "student_id": "School student ID / admission number",
            "learner_id": "National / external learner ID (optional)",
            "nin": "NIN (optional)",
        }
        help_texts = {
            "stream": "Choose a stream if the school uses streams. Learners can also be academically placed through current subject/class enrollments.",
            "student_id": "Use one stable school ID per active learner. EduManage uses it for imports, reports and identity matching.",
            "campus": "For multi-campus institutions, choose the campus explicitly.",
        }
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        campus_queryset = kwargs.pop("campus_queryset", None)
        self.campus_scope = campus
        super().__init__(*args, **kwargs)
        from apps.tenant.academics.models import Stream

        campus_qs = campus_queryset if campus_queryset is not None else Campus.objects.filter(is_active=True)
        campus_qs = campus_qs.filter(is_active=True).order_by("name")
        self.fields["campus"].queryset = campus_qs

        stream_qs = Stream.objects.filter(
            is_active=True,
            class_group__is_active=True,
        ).select_related("class_group", "class_group__campus")
        if campus is not None:
            stream_qs = stream_qs.filter(class_group__campus=campus)
            self.fields["campus"].initial = campus
            self.fields["campus"].required = True
        self.fields["stream"].queryset = stream_qs.order_by("class_group__name", "name")

        if campus is None:
            available = list(campus_qs[:2])
            if len(available) == 1:
                self.campus_scope = available[0]
                self.fields["campus"].initial = available[0]
            elif len(available) > 1:
                self.fields["campus"].required = True

    def _duplicate_active_value(self, field_name, value):
        if not value:
            return False
        qs = StudentProfile.objects.filter(is_active=True, **{f"{field_name}__iexact": value})
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        return qs.exists()

    def clean(self):
        cleaned = super().clean()
        campus = cleaned.get("campus") or self.campus_scope
        stream = cleaned.get("stream")
        is_active = bool(cleaned.get("is_active"))
        student_id = str(cleaned.get("student_id") or "").strip()
        nin = str(cleaned.get("nin") or "").strip()
        learner_id = str(cleaned.get("learner_id") or "").strip()
        dob = cleaned.get("date_of_birth")

        if campus is not None and cleaned.get("campus") is None:
            cleaned["campus"] = campus

        if is_active and not student_id:
            self.add_error("student_id", "Enter the learner's school student ID/admission number before activating the record.")
        elif is_active and self._duplicate_active_value("student_id", student_id):
            self.add_error("student_id", "This student ID is already used by another active learner. Use a unique school ID.")

        if is_active and nin and self._duplicate_active_value("nin", nin):
            self.add_error("nin", "This NIN is already recorded for another active learner. Check the learner record before continuing.")
        if is_active and learner_id and self._duplicate_active_value("learner_id", learner_id):
            self.add_error("learner_id", "This learner ID is already recorded for another active learner.")

        if dob and dob > timezone.localdate():
            self.add_error("date_of_birth", "Date of birth cannot be in the future.")

        if stream:
            stream_campus_id = getattr(stream.class_group, "campus_id", None)
            if campus and stream_campus_id and stream_campus_id != campus.pk:
                self.add_error("stream", "The selected stream belongs to a different campus.")
            elif campus is None and stream_campus_id:
                cleaned["campus"] = stream.class_group.campus

        if is_active and cleaned.get("campus") is None and self.fields["campus"].queryset.count() > 1:
            self.add_error("campus", "Choose the learner's campus. This institution has more than one active campus.")
        return cleaned
