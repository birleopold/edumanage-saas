from django import forms

from .models import AllowanceType, DeductionType, PayGrade, Payslip, SalaryStructure


class PayGradeForm(forms.ModelForm):
    class Meta:
        model = PayGrade
        fields = ["name", "code", "min_salary", "max_salary", "description", "is_active"]


class SalaryStructureForm(forms.ModelForm):
    class Meta:
        model = SalaryStructure
        fields = ["staff", "pay_grade", "base_salary", "effective_date", "end_date", "is_active"]
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }


class AllowanceTypeForm(forms.ModelForm):
    class Meta:
        model = AllowanceType
        fields = ["name", "code", "is_taxable", "is_active"]


class DeductionTypeForm(forms.ModelForm):
    class Meta:
        model = DeductionType
        fields = ["name", "code", "is_percentage", "default_rate", "is_active"]


class PayslipGenerateForm(forms.Form):
    period_year = forms.IntegerField(min_value=2000, max_value=2100, label="Year")
    period_month = forms.IntegerField(min_value=1, max_value=12, label="Month")
    staff = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Select Staff (leave empty for all active staff)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import StaffProfile

        self.fields["staff"].queryset = StaffProfile.objects.filter(is_active=True).order_by("last_name", "first_name")


class PayslipApprovalForm(forms.Form):
    action = forms.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")], widget=forms.RadioSelect)
    comments = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
