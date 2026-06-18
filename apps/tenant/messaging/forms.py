from django import forms

from apps.tenant.academics.models import ClassGroup, Stream
from apps.tenant.orgsettings.models import Campus
from apps.tenant.users.models import Role, User

from .models import Announcement, Conversation, Message


class ConversationForm(forms.Form):
    subject = forms.CharField(max_length=200)
    recipient = forms.ModelChoiceField(queryset=User.objects.none())
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    attachment = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        role_code = kwargs.pop("role_code", "")
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_active=True).exclude(username="")
        if role_code:
            qs = qs.filter(roles__code=role_code)
        self.fields["recipient"].queryset = qs.distinct().order_by("first_name", "last_name", "username")


class MessageReplyForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content", "attachment"]
        widgets = {"content": forms.Textarea(attrs={"rows": 3})}


class BulkMessageForm(forms.Form):
    CHANNEL_CHOICES = (("INBOX", "Internal inbox"), ("SMS", "SMS"), ("WHATSAPP", "WhatsApp"), ("EMAIL", "Email"))
    audience_role = forms.ChoiceField(choices=((Role.PARENT, "Parents"), (Role.STUDENT, "Students"), (Role.TEACHER, "Teachers"), ("ALL", "All users")))
    channel = forms.ChoiceField(choices=CHANNEL_CHOICES)
    campus = forms.ModelChoiceField(queryset=Campus.objects.filter(is_active=True), required=False)
    class_group = forms.ModelChoiceField(queryset=ClassGroup.objects.filter(is_active=True), required=False)
    stream = forms.ModelChoiceField(queryset=Stream.objects.filter(is_active=True), required=False)
    balance_status = forms.ChoiceField(required=False, choices=(("", "Any balance"), ("OUTSTANDING", "Outstanding balance"), ("OVERDUE", "Overdue balance"), ("PAID", "No balance")))
    attendance_status = forms.ChoiceField(required=False, choices=(("", "Any attendance"), ("ABSENT", "Absent today"), ("LATE", "Late today")))
    subject = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))
    dry_run = forms.BooleanField(required=False, initial=False)


class AnnouncementEmailForm(forms.ModelForm):
    send_email = forms.BooleanField(required=False, initial=False)

    class Meta:
        model = Announcement
        fields = ["title", "content", "scope", "audience", "campus", "class_group", "is_urgent", "expires_at", "send_email"]
        widgets = {"expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}
