import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Domain, Tenant
from .onboarding import provision_school_tenant


STATUS_CHOICES = (
    ("active", "Active"),
    ("pending", "Pending setup"),
    ("suspended", "Suspended"),
    ("archived", "Archived"),
)

DOMAIN_TYPE_CHOICES = (
    ("SUBDOMAIN", "Subdomain"),
    ("CUSTOM", "Custom domain"),
)

_RESERVED_SCHEMA_NAMES = {"public", "information_schema", "pg_catalog", "pg_toast"}
_SCHEMA_RE = re.compile(r"^[a-z][a-z0-9_]*$")


ONBOARDING_ONLY_FIELDS = (
    "primary_domain",
    "organization_email",
    "organization_phone",
    "organization_address",
    "owner_first_name",
    "owner_last_name",
    "owner_email",
    "owner_phone",
    "owner_username",
    "owner_temporary_password",
    "owner_temporary_password_confirm",
)


def normalize_domain(value):
    domain = (value or "").strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").strip("/")
    return domain


class StyledFormMixin:
    """Apply consistent Tailwind-friendly classes to platform console forms."""

    default_input_class = (
        "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 "
        "text-sm font-semibold text-slate-900 shadow-sm outline-none "
        "focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
    )
    checkbox_class = "h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", self.checkbox_class)
            else:
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} {self.default_input_class}".strip()


class TenantForm(StyledFormMixin, forms.ModelForm):
    status = forms.ChoiceField(choices=STATUS_CHOICES)
    primary_domain = forms.CharField(
        required=True,
        label="Client domain name",
        help_text="Buy the client's domain, point its DNS to the EduManage server, then enter it here. Example: schoolname.ac.ug",
    )
    organization_email = forms.EmailField(
        required=False,
        label="School email",
        help_text="Optional official school email saved on the organization profile.",
    )
    organization_phone = forms.CharField(
        required=False,
        label="School phone",
        help_text="Optional school contact number saved on the organization profile and main campus.",
    )
    organization_address = forms.CharField(
        required=False,
        label="School address",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional physical address saved on the organization profile and main campus.",
    )
    owner_first_name = forms.CharField(required=False, label="School owner first name")
    owner_last_name = forms.CharField(required=False, label="School owner last name")
    owner_email = forms.EmailField(
        required=True,
        label="School owner/admin email",
        help_text="This account becomes the first admin inside the school's own tenant.",
    )
    owner_phone = forms.CharField(
        required=False,
        max_length=32,
        label="School owner/admin phone",
        help_text="Saved on the owner admin user account for contact and support.",
    )
    owner_username = forms.CharField(
        required=False,
        label="School owner/admin username",
        help_text="Leave blank to use schema_admin, for example greenhill_school_admin.",
    )
    owner_temporary_password = forms.CharField(
        label="Temporary password",
        widget=forms.PasswordInput,
        help_text="Give this temporary password to the school owner. They must change it after first login.",
    )
    owner_temporary_password_confirm = forms.CharField(
        label="Confirm temporary password",
        widget=forms.PasswordInput,
    )

    class Meta:
        model = Tenant
        fields = ("name", "schema_name", "status")
        help_texts = {
            "schema_name": "Lowercase letters, numbers and underscores only. Example: greenhill_school",
            "status": "Suspended tenants remain in the system but should not be treated as active schools.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.onboarding_result = None
        self._style_fields()
        if self.instance and self.instance.pk:
            self.fields["schema_name"].disabled = True
            self.fields["schema_name"].help_text = "Schema name is locked after tenant creation to protect tenant data."
            for field_name in ONBOARDING_ONLY_FIELDS:
                self.fields.pop(field_name, None)

    def clean_schema_name(self):
        schema_name = (self.cleaned_data.get("schema_name") or "").strip().lower()
        if not schema_name:
            raise forms.ValidationError("Schema name is required.")
        if schema_name in _RESERVED_SCHEMA_NAMES:
            raise forms.ValidationError("This schema name is reserved and cannot be used.")
        if not _SCHEMA_RE.match(schema_name):
            raise forms.ValidationError("Use lowercase letters, numbers and underscores only, starting with a letter.")

        qs = Tenant.objects.filter(schema_name=schema_name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A tenant with this schema name already exists.")
        return schema_name

    def clean_primary_domain(self):
        domain = normalize_domain(self.cleaned_data.get("primary_domain"))
        if not domain or "." not in domain:
            raise forms.ValidationError("Enter a valid domain name.")
        if "/" in domain:
            raise forms.ValidationError("Enter the domain only, without paths.")
        if Domain.objects.filter(domain=domain).exists():
            raise forms.ValidationError("This domain is already assigned to another tenant.")
        return domain

    def clean_owner_username(self):
        username = (self.cleaned_data.get("owner_username") or "").strip().lower()
        if username and not re.match(r"^[a-zA-Z0-9_@.+-]+$", username):
            raise forms.ValidationError("Use letters, numbers and @/./+/-/_ characters only.")
        return username

    def clean_owner_temporary_password(self):
        password = self.cleaned_data.get("owner_temporary_password") or ""
        try:
            validate_password(password)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if not (self.instance and self.instance.pk):
            schema_name = cleaned_data.get("schema_name")
            owner_username = cleaned_data.get("owner_username")
            if schema_name and not owner_username:
                cleaned_data["owner_username"] = f"{schema_name}_admin"

            password = cleaned_data.get("owner_temporary_password")
            confirm_password = cleaned_data.get("owner_temporary_password_confirm")
            if password and confirm_password and password != confirm_password:
                self.add_error("owner_temporary_password_confirm", "Temporary passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        if self.instance and self.instance.pk:
            return super().save(commit=commit)

        if not commit:
            return super().save(commit=False)

        with transaction.atomic():
            tenant = super().save(commit=True)
            domain = Domain.objects.create(
                tenant=tenant,
                domain=self.cleaned_data["primary_domain"],
                type="CUSTOM",
                is_primary=True,
            )
            self.onboarding_result = provision_school_tenant(
                tenant=tenant,
                domain=domain,
                organization_email=self.cleaned_data.get("organization_email", ""),
                organization_phone=self.cleaned_data.get("organization_phone", ""),
                organization_address=self.cleaned_data.get("organization_address", ""),
                owner_first_name=self.cleaned_data.get("owner_first_name", ""),
                owner_last_name=self.cleaned_data.get("owner_last_name", ""),
                owner_email=self.cleaned_data["owner_email"],
                owner_phone=self.cleaned_data.get("owner_phone", ""),
                owner_username=self.cleaned_data["owner_username"],
                owner_temporary_password=self.cleaned_data["owner_temporary_password"],
            )
            return tenant


class DomainForm(StyledFormMixin, forms.ModelForm):
    type = forms.ChoiceField(choices=DOMAIN_TYPE_CHOICES)

    class Meta:
        model = Domain
        fields = ("domain", "type", "is_primary")
        help_texts = {
            "domain": "Enter only the host name, for example school.edumanage.com or portal.school.ac.ug.",
            "is_primary": "The primary domain is the main access address for this school.",
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_domain(self):
        domain = normalize_domain(self.cleaned_data.get("domain"))
        if "/" in domain:
            raise forms.ValidationError("Enter the domain only, without paths.")
        if not domain or "." not in domain:
            raise forms.ValidationError("Enter a valid domain name.")

        qs = Domain.objects.filter(domain=domain)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This domain is already assigned to another tenant.")
        return domain

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.tenant is not None:
            obj.tenant = self.tenant
        if commit:
            obj.save()
            if obj.is_primary:
                Domain.objects.filter(tenant=obj.tenant).exclude(pk=obj.pk).update(is_primary=False)
        return obj


class TenantStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={"class": StyledFormMixin.default_input_class}),
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": StyledFormMixin.default_input_class,
                "placeholder": "Optional internal note for this status change.",
            }
        ),
    )


class DomainVerificationForm(forms.Form):
    mark_verified = forms.BooleanField(required=False, initial=True)

    def save(self, domain: Domain):
        if self.cleaned_data.get("mark_verified"):
            domain.verified_at = timezone.now()
            domain.save(update_fields=["verified_at"])
        return domain
