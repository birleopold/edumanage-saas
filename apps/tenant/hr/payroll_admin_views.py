from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from .models import StaffProfile
from .payroll_forms import (
    AllowanceTypeForm,
    DeductionTypeForm,
    PayGradeForm,
    PayslipApprovalForm,
    PayslipGenerateForm,
    SalaryStructureForm,
)
from .payroll_models import (
    AllowanceType,
    DeductionType,
    PayGrade,
    Payslip,
    PayslipAllowance,
    PayslipDeduction,
    PayrollApproval,
    SalaryStructure,
)


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _admin_or_principal_required(request):
    if not request.user.is_authenticated:
        return False
    return request.user.has_role(Role.ADMIN) or request.user.has_role(Role.PRINCIPAL)


def _staff_queryset_for(user):
    qs = StaffProfile.objects.filter(is_active=True).order_by("last_name", "first_name")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(campus=scoped)
    return qs


def _salary_structure_queryset_for(user):
    qs = SalaryStructure.objects.select_related("staff", "staff__campus", "pay_grade")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(staff__campus=scoped)
    return qs


def _payslip_queryset_for(user):
    qs = Payslip.objects.select_related("staff", "staff__campus", "generated_by", "approved_by")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(staff__campus=scoped)
    return qs


# Pay Grade Views
@admin_portal_required
def pay_grade_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = PayGrade.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/payroll/pay_grades_list.html",
        {"pay_grades": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def pay_grade_create(request):
    if request.method == "POST":
        form = PayGradeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pay grade created.")
            return redirect("admin_hr_payroll_pay_grades_list")
    else:
        form = PayGradeForm()

    return render(request, "portals/admin/hr/payroll/pay_grade_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def pay_grade_edit(request, pk: int):
    obj = get_object_or_404(PayGrade, pk=pk)

    if request.method == "POST":
        form = PayGradeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Pay grade updated.")
            return redirect("admin_hr_payroll_pay_grades_list")
    else:
        form = PayGradeForm(instance=obj)

    return render(request, "portals/admin/hr/payroll/pay_grade_form.html", {"form": form, "mode": "edit", "pay_grade": obj})


# Salary Structure Views
@admin_portal_required
def salary_structure_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = _salary_structure_queryset_for(request.user)
    if q:
        qs = qs.filter(Q(staff__first_name__icontains=q) | Q(staff__last_name__icontains=q) | Q(staff__staff_id__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/payroll/salary_structures_list.html",
        {"structures": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def salary_structure_create(request):
    staff_queryset = _staff_queryset_for(request.user)
    if request.method == "POST":
        form = SalaryStructureForm(request.POST, staff_queryset=staff_queryset)
        if form.is_valid():
            form.save()
            messages.success(request, "Salary structure created.")
            return redirect("admin_hr_payroll_salary_structures_list")
    else:
        form = SalaryStructureForm(staff_queryset=staff_queryset)

    return render(request, "portals/admin/hr/payroll/salary_structure_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def salary_structure_edit(request, pk: int):
    staff_queryset = _staff_queryset_for(request.user)
    obj = get_object_or_404(_salary_structure_queryset_for(request.user), pk=pk)

    if request.method == "POST":
        form = SalaryStructureForm(request.POST, instance=obj, staff_queryset=staff_queryset)
        if form.is_valid():
            form.save()
            messages.success(request, "Salary structure updated.")
            return redirect("admin_hr_payroll_salary_structures_list")
    else:
        form = SalaryStructureForm(instance=obj, staff_queryset=staff_queryset)

    return render(request, "portals/admin/hr/payroll/salary_structure_form.html", {"form": form, "mode": "edit", "structure": obj})


# Allowance Type Views
@admin_portal_required
def allowance_type_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = AllowanceType.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/payroll/allowance_types_list.html",
        {"allowance_types": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def allowance_type_create(request):
    if request.method == "POST":
        form = AllowanceTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Allowance type created.")
            return redirect("admin_hr_payroll_allowance_types_list")
    else:
        form = AllowanceTypeForm()

    return render(request, "portals/admin/hr/payroll/allowance_type_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def allowance_type_edit(request, pk: int):
    obj = get_object_or_404(AllowanceType, pk=pk)

    if request.method == "POST":
        form = AllowanceTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Allowance type updated.")
            return redirect("admin_hr_payroll_allowance_types_list")
    else:
        form = AllowanceTypeForm(instance=obj)

    return render(request, "portals/admin/hr/payroll/allowance_type_form.html", {"form": form, "mode": "edit", "allowance_type": obj})


# Deduction Type Views
@admin_portal_required
def deduction_type_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = DeductionType.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/payroll/deduction_types_list.html",
        {"deduction_types": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def deduction_type_create(request):
    if request.method == "POST":
        form = DeductionTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Deduction type created.")
            return redirect("admin_hr_payroll_deduction_types_list")
    else:
        form = DeductionTypeForm()

    return render(request, "portals/admin/hr/payroll/deduction_type_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def deduction_type_edit(request, pk: int):
    obj = get_object_or_404(DeductionType, pk=pk)

    if request.method == "POST":
        form = DeductionTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Deduction type updated.")
            return redirect("admin_hr_payroll_deduction_types_list")
    else:
        form = DeductionTypeForm(instance=obj)

    return render(request, "portals/admin/hr/payroll/deduction_type_form.html", {"form": form, "mode": "edit", "deduction_type": obj})


# Payslip Views
@admin_portal_required
def payslip_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = _payslip_queryset_for(request.user)
    if q:
        qs = qs.filter(Q(staff__first_name__icontains=q) | Q(staff__last_name__icontains=q) | Q(staff__staff_id__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/payroll/payslips_list.html",
        {"payslips": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def payslip_generate(request):
    staff_queryset = _staff_queryset_for(request.user)
    if request.method == "POST":
        form = PayslipGenerateForm(request.POST, staff_queryset=staff_queryset)
        if form.is_valid():
            period_year = form.cleaned_data["period_year"]
            period_month = form.cleaned_data["period_month"]
            selected_staff = form.cleaned_data.get("staff")

            if selected_staff:
                staff_list = selected_staff
            else:
                staff_list = staff_queryset

            created_count = 0
            skipped_count = 0

            with transaction.atomic():
                for staff in staff_list:
                    # Check if payslip already exists
                    if Payslip.objects.filter(staff=staff, period_year=period_year, period_month=period_month).exists():
                        skipped_count += 1
                        continue

                    # Get salary structure
                    try:
                        salary_structure = SalaryStructure.objects.get(staff=staff, is_active=True)
                        base_salary = salary_structure.base_salary
                    except SalaryStructure.DoesNotExist:
                        skipped_count += 1
                        continue

                    # Create payslip
                    payslip = Payslip.objects.create(
                        staff=staff,
                        period_year=period_year,
                        period_month=period_month,
                        base_salary=base_salary,
                        generated_by=request.user,
                        status=Payslip.DRAFT,
                    )

                    # Auto-add default allowances and deductions (you can customize this logic)
                    # For now, just calculate totals
                    payslip.calculate_totals()
                    payslip.save()

                    created_count += 1

            messages.success(request, f"Created {created_count} payslip(s). Skipped {skipped_count}.")
            return redirect("admin_hr_payroll_payslips_list")
    else:
        form = PayslipGenerateForm(staff_queryset=staff_queryset)

    return render(request, "portals/admin/hr/payroll/payslip_generate.html", {"form": form})


@admin_portal_required
def payslip_detail(request, pk: int):
    payslip = get_object_or_404(
        _payslip_queryset_for(request.user).prefetch_related(
            "allowances__allowance_type", "deductions__deduction_type", "approvals"
        ),
        pk=pk,
    )

    return render(request, "portals/admin/hr/payroll/payslip_detail.html", {"payslip": payslip})


@admin_portal_required
def payslip_submit_for_approval(request, pk: int):
    payslip = get_object_or_404(_payslip_queryset_for(request.user), pk=pk)

    if payslip.status != Payslip.DRAFT:
        messages.error(request, "Only draft payslips can be submitted for approval.")
        return redirect("admin_hr_payroll_payslip_detail", pk=payslip.pk)

    with transaction.atomic():
        payslip.status = Payslip.PENDING_APPROVAL
        payslip.save()

        # Create approval records
        PayrollApproval.objects.create(payslip=payslip, approver_role=Role.ADMIN, status=PayrollApproval.PENDING)
        PayrollApproval.objects.create(payslip=payslip, approver_role=Role.PRINCIPAL, status=PayrollApproval.PENDING)

    messages.success(request, "Payslip submitted for approval.")
    return redirect("admin_hr_payroll_payslip_detail", pk=payslip.pk)


def payslip_approve(request, pk: int):
    if not _admin_or_principal_required(request):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Forbidden")

    payslip = get_object_or_404(_payslip_queryset_for(request.user).prefetch_related("approvals"), pk=pk)

    if payslip.status != Payslip.PENDING_APPROVAL:
        messages.error(request, "Only pending payslips can be approved.")
        return redirect("admin_hr_payroll_payslip_detail", pk=payslip.pk)

    user_role = Role.ADMIN if request.user.has_role(Role.ADMIN) else Role.PRINCIPAL

    # Find approval record for this role
    approval = payslip.approvals.filter(approver_role=user_role, status=PayrollApproval.PENDING).first()

    if not approval:
        messages.error(request, "No pending approval for your role.")
        return redirect("admin_hr_payroll_payslip_detail", pk=payslip.pk)

    if request.method == "POST":
        form = PayslipApprovalForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            comments = form.cleaned_data.get("comments", "")

            with transaction.atomic():
                if action == "approve":
                    approval.status = PayrollApproval.APPROVED
                    approval.approver = request.user
                    approval.approved_at = timezone.now()
                    approval.comments = comments
                    approval.save()

                    # Check if all approvals are done
                    if not payslip.approvals.filter(status=PayrollApproval.PENDING).exists():
                        payslip.status = Payslip.APPROVED
                        payslip.approved_by = request.user
                        payslip.approved_at = timezone.now()
                        payslip.save()

                    messages.success(request, "Payslip approved.")
                else:
                    approval.status = PayrollApproval.REJECTED
                    approval.approver = request.user
                    approval.approved_at = timezone.now()
                    approval.comments = comments
                    approval.save()

                    payslip.status = Payslip.REJECTED
                    payslip.save()

                    messages.success(request, "Payslip rejected.")

            return redirect("admin_hr_payroll_payslip_detail", pk=payslip.pk)
    else:
        form = PayslipApprovalForm()

    return render(request, "portals/admin/hr/payroll/payslip_approve.html", {"form": form, "payslip": payslip, "approval": approval})
