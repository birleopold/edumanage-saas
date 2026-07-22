from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.permissions import roles_required
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role

from .models import StaffProfile
from .payroll_models import Payslip


STAFF_PAYSLIP_ROLES = (Role.ADMIN, Role.TEACHER, Role.PRINCIPAL)


def _staff_context(request, **context):
    return {"base_template": base_template_for(request.user), **context}


@roles_required(*STAFF_PAYSLIP_ROLES)
def payslip_list(request):
    staff = StaffProfile.objects.filter(user=request.user).first()
    if not staff:
        return HttpResponseForbidden("No staff profile linked to this account.")

    payslips = (
        Payslip.objects.filter(staff=staff)
        .prefetch_related("allowances__allowance_type", "deductions__deduction_type")
        .order_by("-period_year", "-period_month")
    )

    return render(
        request,
        "portals/staff/payroll/payslips_list.html",
        _staff_context(request, staff=staff, payslips=payslips),
    )


@roles_required(*STAFF_PAYSLIP_ROLES)
def payslip_detail(request, pk: int):
    staff = StaffProfile.objects.filter(user=request.user).first()
    if not staff:
        return HttpResponseForbidden("No staff profile linked to this account.")

    payslip = get_object_or_404(
        Payslip.objects.select_related("staff", "generated_by", "approved_by").prefetch_related(
            "allowances__allowance_type",
            "deductions__deduction_type",
        ),
        pk=pk,
        staff=staff,
    )

    return render(
        request,
        "portals/staff/payroll/payslip_detail.html",
        _staff_context(request, staff=staff, payslip=payslip),
    )
