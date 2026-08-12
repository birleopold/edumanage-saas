from django import forms

from apps.tenant.orgsettings.models import Campus

from .models import TeacherProfile


class TeacherProfileForm(forms.ModelForm):
    create_user = forms.BooleanField(
        required=False,
        initial=True,
        label="Create a teacher portal login",
        help_text="Optional. A teacher can exist in school records without a login until portal access is needed.",
    )
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        label="Email the login details",
        help_text="Only applies when a portal login is created and a usable email address is available.",
    )

    class Meta:
        model = TeacherProfile
        fields = [
            "campus",
            "staff_id",
            "first_name",
            "last_name",
            "phone",
            "email",
            "is_active",
        ]
        labels = {
            "staff_id": "School staff ID (optional)",
        }
        help_texts = {
            "staff_id": "If the school uses staff numbers, keep one stable ID per active teacher. It helps imports, attendance and teaching assignments match the correct person.",
            "campus": "Choose the teacher's normal campus when applicable. Leave blank only for genuinely cross-campus staff.",
        }

    def __init__(self, *args, **kwargs):
        campus_queryset = kwargs.pop("campus_queryset", None)
        campus_scope = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)

        campuses = campus_queryset if campus_queryset is not None else Campus.objects.filter(is_active=True)
        campuses = campuses.filter(is_active=True).order_by("name")
        if campus_scope is not None:
            campuses = campuses.filter(pk=campus_scope.pk)
            self.fields["campus"].initial = campus_scope
        self.fields["campus"].queryset = campuses

        available = list(campuses[:2])
        self.default_campus = campus_scope
        if campus_scope is None and len(available) == 1:
            self.default_campus = available[0]
            self.fields["campus"].initial = available[0]

    def clean(self):
        cleaned = super().clean()
        staff_id = str(cleaned.get("staff_id") or "").strip()
        campus = cleaned.get("campus") or self.default_campus
        is_active = bool(cleaned.get("is_active"))

        if campus is not None and cleaned.get("campus") is None:
            cleaned["campus"] = campus

        if is_active and staff_id:
            duplicate = TeacherProfile.objects.filter(is_active=True, staff_id__iexact=staff_id)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("staff_id", "This staff ID is already used by another active teacher. Use a unique staff ID.")
        return cleaned
