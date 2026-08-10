from django import forms
from django.db.models import Q

from apps.tenant.hr.models import StaffProfile
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .models import AttendanceDailyRecord, AttendanceDevice, AttendanceIdentity, AttendancePolicy


BASE_CLASS = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
CHECK_CLASS = "h-5 w-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500"


class AttendanceDeviceForm(forms.ModelForm):
    class Meta:
        model = AttendanceDevice
        fields = [
            "name",
            "code",
            "serial_number",
            "vendor",
            "model_name",
            "campus",
            "location",
            "connection_mode",
            "protocol",
            "identity_namespace",
            "timezone_name",
            "capabilities",
            "settings",
            "is_active",
        ]
        widgets = {
            "capabilities": forms.Textarea(attrs={"rows": 4}),
            "settings": forms.Textarea(attrs={"rows": 6}),
        }
        help_texts = {
            "code": "Stable code sent by the device or edge connector. Avoid changing it after deployment.",
            "protocol": "Examples: canonical-json, ZKTeco PUSH/ADMS, Hikvision ISAPI, Suprema G-SDK/BioStar, CSV.",
            "identity_namespace": "Use the same namespace when several devices share the same user numbers; use separate namespaces when vendor IDs overlap.",
            "settings": "Advanced JSON: direction_map, fixed_direction, allowed_ips, auto_match_system_ids, clock-skew controls, accepted_event_codes.",
        }

    def __init__(self, *args, campus_scope=None, **kwargs):
        self.campus_scope = campus_scope
        super().__init__(*args, **kwargs)
        org = get_or_create_organization()
        campuses = Campus.objects.filter(organization=org, is_active=True).order_by("name")
        if campus_scope is not None:
            campuses = campuses.filter(pk=campus_scope.pk)
            self.fields["campus"].initial = campus_scope
            self.fields["campus"].required = True
        self.fields["campus"].queryset = campuses
        for name, field in self.fields.items():
            field.widget.attrs["class"] = CHECK_CLASS if isinstance(field.widget, forms.CheckboxInput) else BASE_CLASS
        if self.instance and self.instance.pk:
            self.fields["code"].disabled = True

    def clean(self):
        cleaned = super().clean()
        campus = cleaned.get("campus")
        namespace = str(cleaned.get("identity_namespace") or "").strip()
        if not campus or not namespace:
            return cleaned

        # Several devices inside one campus may intentionally share the same
        # namespace/user list. A campus-bound device must not share that
        # namespace with a different campus or with a global/unassigned device,
        # because the same external user ID could otherwise resolve to the wrong
        # person. Global devices remain possible by leaving this device unscoped.
        conflicting_device = (
            AttendanceDevice.objects.filter(identity_namespace=namespace)
            .exclude(pk=self.instance.pk)
            .exclude(campus=campus)
            .first()
        )
        if conflicting_device:
            scope = conflicting_device.campus.name if conflicting_device.campus_id else "a global/unassigned device"
            self.add_error(
                "identity_namespace",
                f"This identity namespace is already used by {scope}. Use a campus-specific namespace to prevent user-ID collisions.",
            )
            return cleaned

        cross_campus_identity = AttendanceIdentity.objects.filter(namespace=namespace, is_active=True).filter(
            (Q(student__isnull=False) & ~Q(student__campus=campus))
            | (Q(staff__isnull=False) & ~Q(staff__campus=campus))
        )
        if cross_campus_identity.exists():
            self.add_error(
                "identity_namespace",
                "This namespace already contains an active person mapping from another campus. Choose a different namespace or review the existing mappings first.",
            )
        return cleaned


class AttendanceIdentityForm(forms.ModelForm):
    class Meta:
        model = AttendanceIdentity
        fields = ["external_person_id", "person_type", "student", "staff", "card_number", "is_active"]
        help_texts = {
            "external_person_id": "The user number/PIN/employee number stored in the attendance device.",
            "card_number": "Optional physical card number for reference. Device user ID remains the canonical mapping key.",
        }

    def __init__(self, *args, device: AttendanceDevice, **kwargs):
        self.device = device
        super().__init__(*args, **kwargs)
        students = StudentProfile.objects.filter(is_active=True).order_by("last_name", "first_name")
        staff = StaffProfile.objects.filter(is_active=True).order_by("last_name", "first_name")
        if device.campus_id:
            students = students.filter(campus_id=device.campus_id)
            staff = staff.filter(campus_id=device.campus_id)
        self.fields["student"].queryset = students
        self.fields["staff"].queryset = staff
        for name, field in self.fields.items():
            field.widget.attrs["class"] = CHECK_CLASS if isinstance(field.widget, forms.CheckboxInput) else BASE_CLASS

    def clean(self):
        cleaned = super().clean()
        person_type = cleaned.get("person_type")
        student = cleaned.get("student")
        staff = cleaned.get("staff")
        if person_type == AttendanceIdentity.STUDENT:
            if not student:
                self.add_error("student", "Select the student represented by this device user ID.")
            if staff:
                self.add_error("staff", "Leave staff blank for a student identity.")
        elif person_type == AttendanceIdentity.STAFF:
            if not staff:
                self.add_error("staff", "Select the staff member represented by this device user ID.")
            if student:
                self.add_error("student", "Leave student blank for a staff identity.")
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        item.namespace = self.device.identity_namespace
        item.source = item.source or "MANUAL"
        if commit:
            item.full_clean()
            item.save()
        return item


class AttendancePolicyForm(forms.ModelForm):
    class Meta:
        model = AttendancePolicy
        fields = [
            "name",
            "campus",
            "person_type",
            "expected_in",
            "expected_out",
            "late_grace_minutes",
            "early_departure_grace_minutes",
            "duplicate_window_seconds",
            "minimum_presence_minutes",
            "direction_strategy",
            "weekdays",
            "notify_parent_on_arrival",
            "notify_parent_on_departure",
            "is_default",
            "is_active",
            "settings",
        ]
        widgets = {
            "expected_in": forms.TimeInput(attrs={"type": "time"}),
            "expected_out": forms.TimeInput(attrs={"type": "time"}),
            "weekdays": forms.TextInput(attrs={"placeholder": "[0,1,2,3,4]"}),
            "settings": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "minimum_presence_minutes": "Set 0 to disable minimum-duration checks.",
            "direction_strategy": "FIRST_LAST is safest for cheap devices that do not identify IN versus OUT.",
            "weekdays": "Monday=0, Tuesday=1 ... Sunday=6. Leave [] for Monday-Friday.",
        }

    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        org = get_or_create_organization()
        campuses = Campus.objects.filter(organization=org, is_active=True).order_by("name")
        if campus_scope is not None:
            campuses = campuses.filter(pk=campus_scope.pk)
            self.fields["campus"].initial = campus_scope
            self.fields["campus"].required = True
        self.fields["campus"].queryset = campuses
        for name, field in self.fields.items():
            field.widget.attrs["class"] = CHECK_CLASS if isinstance(field.widget, forms.CheckboxInput) else BASE_CLASS


class AttendanceCSVImportForm(forms.Form):
    device = forms.ModelChoiceField(queryset=AttendanceDevice.objects.none())
    file = forms.FileField(help_text="CSV headers are auto-detected from common vendor names such as person_id/PIN/userID and timestamp/Time/dateTime.")
    auto_match_system_ids = forms.BooleanField(
        required=False,
        help_text="Create mappings automatically only when the device user ID exactly matches one active student ID or staff ID.",
    )

    def __init__(self, *args, user_campus=None, **kwargs):
        super().__init__(*args, **kwargs)
        devices = AttendanceDevice.objects.filter(is_active=True).order_by("name")
        if user_campus is not None:
            devices = devices.filter(campus=user_campus)
        self.fields["device"].queryset = devices
        for name, field in self.fields.items():
            field.widget.attrs["class"] = CHECK_CLASS if isinstance(field.widget, forms.CheckboxInput) else BASE_CLASS

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > 20 * 1024 * 1024:
            raise forms.ValidationError("CSV attendance imports must be 20 MB or smaller.")
        if not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        return upload


class AttendanceManualAdjustmentForm(forms.Form):
    status = forms.ChoiceField(choices=AttendanceDailyRecord.STATUS_CHOICES)
    first_in = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    last_out = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    note = forms.CharField(required=False, max_length=255, widget=forms.Textarea(attrs={"rows": 2}))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), help_text="Required audit reason for changing an attendance record.")

    def __init__(self, *args, record=None, **kwargs):
        super().__init__(*args, **kwargs)
        if record is not None and not self.is_bound:
            self.fields["status"].initial = record.status
            self.fields["first_in"].initial = record.first_in
            self.fields["last_out"].initial = record.last_out
            self.fields["note"].initial = record.note
        for field in self.fields.values():
            field.widget.attrs["class"] = BASE_CLASS

    def clean(self):
        cleaned = super().clean()
        first_in = cleaned.get("first_in")
        last_out = cleaned.get("last_out")
        if first_in and last_out and last_out < first_in:
            self.add_error("last_out", "Last out cannot be earlier than first in.")
        return cleaned
