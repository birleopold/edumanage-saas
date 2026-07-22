from django import forms
from django.db.models import Q

from apps.tenant.academics.models import ClassGroup, Stream
from apps.tenant.orgsettings.models import Campus
from apps.tenant.users.models import Role, User

from .models import Announcement, Message


VALID_ROLE_CODES = {code for code, _label in Role.CODE_CHOICES}
FINANCE_TOPIC = "finance"


class RecipientChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        name = (obj.get_full_name() or obj.username).strip()
        role_names = [role.name for role in obj.roles.all()]
        role_label = ", ".join(role_names)
        return f"{name} — {role_label}" if role_label else name


def _user_role_codes(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(user.roles.values_list("code", flat=True))


def _user_campus_ids(user):
    """Resolve campus scope from authoritative role and profile records."""

    campus_ids = set(
        user.userrole_set.exclude(campus_id__isnull=True).values_list(
            "campus_id", flat=True
        )
    )
    user_row = User.objects.filter(pk=user.pk)
    campus_ids.update(
        campus_id
        for campus_id in user_row.values_list(
            "student_profile__campus_id", flat=True
        )
        if campus_id
    )
    campus_ids.update(
        campus_id
        for campus_id in user_row.values_list(
            "teacher_profile__campus_id", flat=True
        )
        if campus_id
    )
    campus_ids.update(
        campus_id
        for campus_id in user_row.values_list(
            "staff_profile__campus_id", flat=True
        )
        if campus_id
    )
    campus_ids.update(
        campus_id
        for campus_id in user_row.values_list(
            "parent_profile__parentstudentlink__student__campus_id", flat=True
        )
        if campus_id
    )
    return campus_ids


def _campus_membership_filter(campus_ids):
    return (
        Q(userrole__campus_id__in=campus_ids)
        | Q(student_profile__campus_id__in=campus_ids)
        | Q(teacher_profile__campus_id__in=campus_ids)
        | Q(staff_profile__campus_id__in=campus_ids)
        | Q(
            parent_profile__parentstudentlink__student__campus_id__in=campus_ids
        )
        | Q(roles__code=Role.ADMIN)
    )


def _finance_recipient_filter():
    finance_terms = (
        Q(staff_profile__department__name__icontains="finance")
        | Q(staff_profile__department__name__icontains="account")
        | Q(staff_profile__department__code__iexact="FIN")
        | Q(staff_profile__department__code__iexact="ACC")
        | Q(staff_profile__position__title__icontains="bursar")
        | Q(staff_profile__position__title__icontains="account")
        | Q(staff_profile__position__title__icontains="finance")
    )
    return finance_terms | Q(
        roles__code__in=(Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL)
    )


def recipient_queryset_for(user, *, role_code="", topic=""):
    """Return only recipients the sender is authorised to contact."""

    queryset = (
        User.objects.filter(is_active=True)
        .exclude(pk=user.pk)
        .exclude(username="")
        .prefetch_related("roles")
    )
    sender_roles = _user_role_codes(user)
    is_global_admin = bool(getattr(user, "is_superuser", False)) or Role.ADMIN in sender_roles

    if topic == FINANCE_TOPIC:
        queryset = queryset.filter(_finance_recipient_filter())
    elif not is_global_admin:
        if sender_roles.intersection({Role.PARENT, Role.STUDENT}):
            allowed_roles = {
                Role.ADMIN,
                Role.CAMPUS_ADMIN,
                Role.PRINCIPAL,
                Role.TEACHER,
            }
        elif Role.TEACHER in sender_roles:
            allowed_roles = {
                Role.ADMIN,
                Role.CAMPUS_ADMIN,
                Role.PRINCIPAL,
                Role.PARENT,
                Role.STUDENT,
            }
        elif sender_roles.intersection({Role.CAMPUS_ADMIN, Role.PRINCIPAL}):
            allowed_roles = VALID_ROLE_CODES
        else:
            allowed_roles = set()

        if role_code in VALID_ROLE_CODES:
            allowed_roles &= {role_code}
        queryset = queryset.filter(roles__code__in=allowed_roles)
    elif role_code in VALID_ROLE_CODES:
        queryset = queryset.filter(roles__code=role_code)

    if not is_global_admin:
        campus_ids = _user_campus_ids(user)
        if campus_ids:
            queryset = queryset.filter(_campus_membership_filter(campus_ids))
        else:
            queryset = queryset.filter(roles__code=Role.ADMIN)

    return queryset.distinct().order_by("first_name", "last_name", "username")


class ConversationForm(forms.Form):
    subject = forms.CharField(max_length=200)
    recipient = RecipientChoiceField(queryset=User.objects.none())
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))
    attachment = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        role_code = (kwargs.pop("role_code", "") or "").strip().upper()
        topic = (kwargs.pop("topic", "") or "").strip().lower()
        current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

        if current_user is None:
            recipient_queryset = User.objects.none()
        else:
            recipient_queryset = recipient_queryset_for(
                current_user,
                role_code=role_code,
                topic=topic,
            )
        self.fields["recipient"].queryset = recipient_queryset
        self.fields["recipient"].empty_label = "Choose a recipient"
        self.fields["recipient"].help_text = (
            "Choose an authorised finance-office or school administration contact."
            if topic == FINANCE_TOPIC
            else "Only school users you are authorised to contact are listed."
        )

        shared_class = (
            "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 "
            "text-sm font-semibold text-slate-900 outline-none focus:border-primary-500 "
            "focus:ring-4 focus:ring-primary-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = shared_class
        self.fields["attachment"].widget.attrs["class"] = (
            "block w-full rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 "
            "px-4 py-3 text-sm text-slate-700 focus:border-primary-500 focus:ring-4 "
            "focus:ring-primary-100"
        )


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
