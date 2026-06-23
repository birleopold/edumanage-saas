import re

from django import forms

from .forms import STATUS_CHOICES, normalize_domain
from .models import Domain, Tenant
from .onboarding import DEFAULT_FEATURE_FLAGS


FEATURE_LABELS = {
    "academics": "Academics",
    "admissions": "Admissions",
    "attendance": "Attendance",
    "assessments": "Assessments",
    "announcements": "Announcements",
    "coursework": "Coursework",
    "students": "Students",
    "teachers": "Teachers",
    "parents": "Parents",
    "finance": "Finance",
    "library": "Library",
    "transport": "Transport",
    "hostels": "Hostels",
    "inventory": "Inventory",
    "documents": "Documents",
    "timetable": "Timetable",
    "exams": "Exams",
    "reports": "Reports",
    "messaging": "Messaging",
    "hr": "HR",
    "analytics": "Analytics",
    "audit": "Audit",
}

FEATURE_CHOICES = tuple((code, FEATURE_LABELS.get(code, code.replace("_", " ").title())) for code, _enabled in DEFAULT_FEATURE_FLAGS)

FEATURE_PACKAGES = {
    "starter": {
        "label": "Starter",
        "features": ("academics", "students", "teachers", "parents", "attendance", "announcements", "documents"),
    },
    "standard": {
        "label": "Standard",
        "features": (
            "academics",
            "admissions",
            "attendance",
            "assessments",
            "announcements",
            "coursework",
            "students",
            "teachers",
            "parents",
            "finance",
            "documents",
            "timetable",
            "exams",
            "reports",
        ),
    },
    "enterprise": {
        "label": "Enterprise",
        "features": tuple(code for code, _enabled in DEFAULT_FEATURE_FLAGS),
    },
    "custom": {
        "label": "Custom",
        "features": (),
    },
}

PACKAGE_CHOICES = tuple((code, config["label"]) for code, config in FEATURE_PACKAGES.items())
_RESERVED_SCHEMA_NAMES = {"public", "information_schema", "pg_catalog", "pg_toast"}
_SCHEMA_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_@.+-]+$")


class WizardStyledFormMixin:
    input_class = (
        "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 "
        "text-sm font-semibold text-slate-900 shadow-sm outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
    )
    checkbox_class = "h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", self.checkbox_class)
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs.setdefault("class", "space-y-2")
            else:
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {self.input_class}".strip()


class SchoolDetailsStepForm(WizardStyledFormMixin, forms.Form):
    name = forms.CharField(label="School/client name", max_length=255)
    schema_name = forms.CharField(
        label="Tenant schema/slug",
        max_length=63,
        help_text="Lowercase letters, numbers and underscores only. Example: greenhill_school",
    )
    status = forms.ChoiceField(choices=STATUS_CHOICES, initial="active")
    organization_email = forms.EmailField(required=False, label="School email")
    organization_phone = forms.CharField(required=False, label="School phone", max_length=32)
    organization_address = forms.CharField(required=False, label="School address", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_schema_name(self):
        schema_name = (self.cleaned_data.get("schema_name") or "").strip().lower()
        if not schema_name:
            raise forms.ValidationError("Schema name is required.")
        if schema_name in _RESERVED_SCHEMA_NAMES:
            raise forms.ValidationError("This schema name is reserved and cannot be used.")
        if not _SCHEMA_RE.match(schema_name):
            raise forms.ValidationError("Use lowercase letters, numbers and underscores only, starting with a letter.")
        if Tenant.objects.filter(schema_name=schema_name).exists():
            raise forms.ValidationError("A tenant with this schema name already exists.")
        return schema_name


class DomainDetailsStepForm(WizardStyledFormMixin, forms.Form):
    domain = forms.CharField(
        label="School login domain",
        help_text="Enter only the host name, for example schoolname.ac.ug or school.edumanage.com.",
    )
    domain_type = forms.ChoiceField(
        choices=(("CUSTOM", "Custom domain"), ("SUBDOMAIN", "Subdomain")),
        initial="CUSTOM",
        label="Domain type",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_domain(self):
        domain = normalize_domain(self.cleaned_data.get("domain"))
        if not domain or "." not in domain:
            raise forms.ValidationError("Enter a valid domain name.")
        if "/" in domain:
            raise forms.ValidationError("Enter the domain only, without paths.")
        if Domain.objects.filter(domain=domain).exists():
            raise forms.ValidationError("This domain is already assigned to another tenant.")
        return domain


class OwnerAdminStepForm(WizardStyledFormMixin, forms.Form):
    owner_first_name = forms.CharField(required=False, label="Owner/admin first name")
    owner_last_name = forms.CharField(required=False, label="Owner/admin last name")
    owner_email = forms.EmailField(label="Owner/admin email")
    owner_username = forms.CharField(
        required=False,
        label="Owner/admin username",
        help_text="Leave blank to use schema_admin, for example greenhill_school_admin.",
    )

    def __init__(self, *args, schema_name=None, **kwargs):
        self.schema_name = schema_name
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_owner_username(self):
        username = (self.cleaned_data.get("owner_username") or "").strip().lower()
        if not username and self.schema_name:
            username = f"{self.schema_name}_admin"
        if username and not _USERNAME_RE.match(username):
            raise forms.ValidationError("Use letters, numbers and @/./+/-/_ characters only.")
        return username


class PackageFeaturesStepForm(WizardStyledFormMixin, forms.Form):
    package = forms.ChoiceField(choices=PACKAGE_CHOICES, initial="standard", label="Package")
    feature_flags = forms.MultipleChoiceField(
        required=False,
        choices=FEATURE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Enabled modules/features",
        help_text="For Starter, Standard and Enterprise, the package presets are applied automatically. Choose Custom to manually control features.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("feature_flags"):
            self.initial["feature_flags"] = FEATURE_PACKAGES["standard"]["features"]
        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        package = cleaned_data.get("package") or "standard"
        selected_features = tuple(cleaned_data.get("feature_flags") or ())
        if package != "custom":
            selected_features = FEATURE_PACKAGES[package]["features"]
        if not selected_features:
            raise forms.ValidationError("Select at least one module or choose a package preset.")
        cleaned_data["feature_flags"] = selected_features
        cleaned_data["package_label"] = FEATURE_PACKAGES[package]["label"]
        return cleaned_data


class ConfirmActivationStepForm(WizardStyledFormMixin, forms.Form):
    confirm_activation = forms.BooleanField(
        label="I confirm this school should be created and activated now.",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
