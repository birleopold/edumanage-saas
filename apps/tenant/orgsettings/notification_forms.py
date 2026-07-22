from django import forms
from django.contrib.auth import get_user_model

from apps.tenant.orgsettings.models import Campus, Notification

from .notification_state import is_safe_notification_link


NOTIFICATION_TYPE_CHOICES = (
    ("URGENT_ALERT", "Urgent alert"),
    ("FEE_REMINDER", "Fee reminder"),
    ("EXAM_ALERT", "Exam alert"),
    ("TRANSPORT_ALERT", "Transport alert"),
    ("SYSTEM_NOTICE", "System notice"),
)


class NotificationComposerForm(forms.Form):
    notification_type = forms.ChoiceField(
        choices=NOTIFICATION_TYPE_CHOICES,
        initial="SYSTEM_NOTICE",
    )
    title = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))
    priority = forms.ChoiceField(
        choices=Notification.PRIORITY_CHOICES,
        initial=Notification.NORMAL,
    )
    audience = forms.ChoiceField(
        choices=Notification.AUDIENCE_CHOICES,
        initial=Notification.ALL,
    )
    campus = forms.ModelChoiceField(queryset=Campus.objects.none(), required=False)
    recipient = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
    )
    link = forms.CharField(
        max_length=255,
        required=False,
        help_text="Optional same-school portal path, for example /student/finance/ or /teacher/exams/.",
    )
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    field_class = (
        "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 text-sm "
        "font-semibold text-slate-900 shadow-sm outline-none focus:border-blue-500 "
        "focus:ring-4 focus:ring-blue-100"
    )

    def __init__(self, *args, campus_queryset=None, user_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["campus"].queryset = (
            campus_queryset
            if campus_queryset is not None
            else Campus.objects.filter(is_active=True).order_by("name")
        )
        self.fields["recipient"].queryset = (
            user_queryset
            if user_queryset is not None
            else get_user_model()
            .objects.filter(is_active=True)
            .order_by("first_name", "last_name", "username")
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = self.field_class

    def clean_link(self):
        link = (self.cleaned_data.get("link") or "").strip()
        if not is_safe_notification_link(link):
            raise forms.ValidationError(
                "Use a same-school portal path that starts with one slash, such as /student/finance/."
            )
        return link
