from django import forms

from .models import TeacherProfile


class TeacherProfileForm(forms.ModelForm):
    create_user = forms.BooleanField(required=False, initial=True)
    send_email = forms.BooleanField(required=False, initial=True)

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
