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
            "is_active",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }
