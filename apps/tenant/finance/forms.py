from django import forms

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Stream
from apps.tenant.orgsettings.models import Campus
from apps.tenant.students.models import StudentProfile

from .models import FeeItem, Invoice, InvoiceLine, Payment


class FeeItemForm(forms.ModelForm):
    class Meta:
        model = FeeItem
        fields = ["code", "name", "amount", "is_active"]


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "student",
            "academic_year",
            "academic_term",
            "reference",
            "due_date",
            "opening_balance",
            "status",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)
        if campus is not None:
            self.fields["student"].queryset = StudentProfile.objects.filter(campus=campus)


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["fee_item", "description", "quantity", "unit_amount"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "mobile_network", "reference", "received_at"]
        widgets = {
            "received_at": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get("amount")
        if amount is not None and amount <= 0:
            self.add_error("amount", "Payment amount must be greater than zero.")
        if cleaned.get("method") != Payment.MOBILE:
            cleaned["mobile_network"] = ""
        return cleaned


class CarryForwardForm(forms.Form):
    target_year = forms.ModelChoiceField(
        label="Target academic year",
        queryset=AcademicYear.objects.none(),
        required=True,
    )
    target_term = forms.ModelChoiceField(
        label="Target term",
        queryset=AcademicTerm.objects.select_related("year"),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_year"].queryset = AcademicYear.objects.all().order_by("-name")
        self.fields["target_term"].queryset = AcademicTerm.objects.select_related("year").order_by(
            "-year__name", "order"
        )

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("target_year")
        term = cleaned.get("target_term")
        if year and term and term.year_id != year.pk:
            raise forms.ValidationError("The selected term must belong to the selected academic year.")
        return cleaned


def _campus_scope_ids(campus_scope):
    if campus_scope is None:
        return None
    if isinstance(campus_scope, Campus):
        return [campus_scope.id]
    try:
        return [campus.id for campus in campus_scope]
    except TypeError:
        return [campus_scope.id]


class BulkInvoiceForm(forms.Form):
    campus = forms.ModelChoiceField(
        queryset=Campus.objects.none(),
        required=False,
        help_text="Optional: limit billing to one campus.",
    )
    class_group = forms.ModelChoiceField(
        queryset=ClassGroup.objects.none(),
        required=False,
        help_text="Optional: limit billing to one class.",
    )
    stream = forms.ModelChoiceField(
        queryset=Stream.objects.none(),
        required=False,
        help_text="Optional: limit billing to one stream.",
    )
    students = forms.ModelMultipleChoiceField(
        queryset=StudentProfile.objects.none(),
        required=False,
        help_text="Optional: select specific students. Leave blank to bill all students matching the filters above.",
    )
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.none(), required=True)
    academic_term = forms.ModelChoiceField(queryset=AcademicTerm.objects.none(), required=True)
    due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    fee_items = forms.ModelMultipleChoiceField(
        queryset=FeeItem.objects.none(),
        required=True,
        help_text="Select one or more fee items to appear as invoice line items.",
    )
    opening_balance = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
        help_text="Optional same opening balance to add to each generated invoice.",
    )
    reference_prefix = forms.CharField(max_length=16, required=False, initial="INV")
    skip_existing = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Skip students who already have an invoice for the selected academic year and term.",
    )

    def __init__(self, *args, **kwargs):
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)

        campus_qs = Campus.objects.filter(is_active=True).order_by("name")
        students_qs = StudentProfile.objects.filter(is_active=True).select_related("campus", "stream", "stream__class_group")
        class_qs = ClassGroup.objects.filter(is_active=True).select_related("campus", "level", "program").order_by("name")
        stream_qs = Stream.objects.filter(is_active=True).select_related("class_group").order_by("class_group__name", "name")

        campus_ids = _campus_scope_ids(campus_scope)
        if campus_ids is not None:
            campus_qs = campus_qs.filter(id__in=campus_ids)
            students_qs = students_qs.filter(campus_id__in=campus_ids)
            class_qs = class_qs.filter(campus_id__in=campus_ids)
            stream_qs = stream_qs.filter(class_group__campus_id__in=campus_ids)

        self.fields["campus"].queryset = campus_qs
        self.fields["students"].queryset = students_qs.order_by("last_name", "first_name")
        self.fields["class_group"].queryset = class_qs
        self.fields["stream"].queryset = stream_qs
        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by("-name")
        self.fields["academic_term"].queryset = AcademicTerm.objects.select_related("year").order_by("-year__name", "order")
        self.fields["fee_items"].queryset = FeeItem.objects.filter(is_active=True).order_by("name")

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("academic_year")
        term = cleaned.get("academic_term")
        campus = cleaned.get("campus")
        class_group = cleaned.get("class_group")
        stream = cleaned.get("stream")

        if year and term and term.year_id != year.pk:
            self.add_error("academic_term", "The selected term must belong to the selected academic year.")

        if campus and class_group and class_group.campus_id and class_group.campus_id != campus.id:
            self.add_error("class_group", "The selected class does not belong to the selected campus.")

        if class_group and stream and stream.class_group_id != class_group.id:
            self.add_error("stream", "The selected stream does not belong to the selected class.")

        if campus and stream and stream.class_group.campus_id and stream.class_group.campus_id != campus.id:
            self.add_error("stream", "The selected stream does not belong to the selected campus.")

        return cleaned

    def matching_students(self):
        selected_students = self.cleaned_data.get("students")
        if selected_students:
            qs = selected_students
        else:
            qs = StudentProfile.objects.filter(is_active=True).select_related("campus", "stream", "stream__class_group")

        campus = self.cleaned_data.get("campus")
        class_group = self.cleaned_data.get("class_group")
        stream = self.cleaned_data.get("stream")

        if campus:
            qs = qs.filter(campus=campus)
        if class_group:
            qs = qs.filter(stream__class_group=class_group)
        if stream:
            qs = qs.filter(stream=stream)
        return qs.order_by("last_name", "first_name")
