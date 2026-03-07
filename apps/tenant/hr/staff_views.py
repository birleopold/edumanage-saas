from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import StaffProfile
from .payroll_models import Payslip


@role_required([Role.ADMIN, Role.TEACHER, Role.PRINCIPAL])
def payslip_list(request):
    # Get staff profile for current user
    staff = StaffProfile.objects.filter(user=request.user).first()
    if not staff:
        return HttpResponseForbidden("No staff profile linked to this account.")

    payslips = Payslip.objects.filter(staff=staff).prefetch_related("allowances__allowance_type", "deductions__deduction_type").order_by("-period_year", "-period_month")

    return render(request, "portals/staff/payroll/payslips_list.html", {"staff": staff, "payslips": payslips})


@role_required([Role.ADMIN, Role.TEACHER, Role.PRINCIPAL])
def payslip_detail(request, pk: int):
    # Get staff profile for current user
    staff = StaffProfile.objects.filter(user=request.user).first()
    if not staff:
        return HttpResponseForbidden("No staff profile linked to this account.")

    payslip = get_object_or_404(
        Payslip.objects.select_related("staff", "generated_by", "approved_by").prefetch_related("allowances__allowance_type", "deductions__deduction_type"),
        pk=pk,
        staff=staff,
    )

    return render(request, "portals/staff/payroll/payslip_detail.html", {"staff": staff, "payslip": payslip})
