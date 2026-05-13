from django import forms

from .models import StudentProfile


class StudentProfileForm(forms.ModelForm):
    create_user = forms.BooleanField(required=False, initial=True)
    send_email = forms.BooleanField(required=False, initial=True)

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
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)
        from apps.tenant.academics.models import Stream

        stream_qs = Stream.objects.filter(is_active=True).select_related("class_group")
        if campus is not None:
            stream_qs = stream_qs.filter(class_group__campus=campus)
        self.fields["stream"].queryset = stream_qs
