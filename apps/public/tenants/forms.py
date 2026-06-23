import re

from django import forms
from django.db import transaction
from django.utils import timezone

from .models import Domain, Tenant


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


def normalize_domain(value):
    domain = (value or "").strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").strip("/")
    return domain


def seed_organization_profile_from_tenant(tenant):
    """Create the school-facing profile for this tenant.

    Tenant is the platform SaaS record. OrganizationProfile is the school record
    used inside that tenant. In full PostgreSQL tenant mode every tenant has its
    own schema and therefore its own OrganizationProfile table. In local SQLite
    development there is one shared database, so we create one profile per tenant
    name to make the relationship visible in dj-admin without overwriting the
    previous school profile.
    """
    try:
        from apps.tenant.orgsettings.models import Campus, OrganizationProfile
    except Exception:
        return

    primary_domain = Domain.objects.filter(tenant=tenant, is_primary=True).order_by("id").first()
    if primary_domain is None:
        primary_domain = Domain.objects.filter(tenant=tenant).order_by("id").first()

    profile = OrganizationProfile.objects.filter(name=tenant.name).order_by("id").first()
    defaults = {
        "legal_name": tenant.name,
        "tenant_schema_name": tenant.schema_name,
        "tenant_domain": primary_domain.domain if primary_domain else "",
        "tenant_status": tenant.status,
    }
    if profile is None:
        profile = OrganizationProfile.objects.create(name=tenant.name, **defaults)
    else:
        changed_fields = []
        for field, value in defaults.items():
            if value and getattr(profile, field, None) != value:
                setattr(profile, field, value)
                changed_fields.append(field)
        if changed_fields:
            changed_fields.append("updated_at")
            profile.save(update_fields=changed_fields)

    Campus.objects.get_or_create(
        organization=profile,
        is_default=True,
        defaults={"name": "Main Campus", "is_active": True},
    )


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

    class Meta:
        model = Tenant
        fields = ("name", "schema_name", "status")
        help_texts = {
            "schema_name": "Lowercase letters, numbers and underscores only. Example: greenhill_school",
            "status": "Suspended tenants remain in the system but should not be treated as active schools.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        if self.instance and self.instance.pk:
            self.fields["schema_name"].disabled = True
            self.fields["schema_name"].help_text = "Schema name is locked after tenant creation to protect tenant data."
            self.fields.pop("primary_domain", None)

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

    def save(self, commit=True):
        if self.instance and self.instance.pk:
            tenant = super().save(commit=commit)
            if commit:
                seed_organization_profile_from_tenant(tenant)
            return tenant

        if not commit:
            return super().save(commit=False)

        with transaction.atomic():
            tenant = super().save(commit=True)
            Domain.objects.create(
                tenant=tenant,
                domain=self.cleaned_data["primary_domain"],
                type="CUSTOM",
                is_primary=True,
            )
            seed_organization_profile_from_tenant(tenant)
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
