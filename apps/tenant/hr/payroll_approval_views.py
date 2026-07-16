from io import BytesIO

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apps.tenant.orgsettings.models import Notification
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import roles_required
from apps.tenant.users.models import Role

from .payroll_models import Payslip, PayrollApproval


PAYROLL_REVIEW_ROLES = (Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL)

ROLE_ALIASES = {
    "BURSAR": (Role.ADMIN, Role.CAMPUS_ADMIN),
    "HEADTEACHER": (Role.PRINCIPAL,),
    "DIRECTOR": (Role.ADMIN,),
    "ADMIN": (Role.ADMIN,),
    "PRINCIPAL": (Role.PRINCIPAL,),
    "CAMPUS_ADMIN": (Role.CAMPUS_ADMIN,),
}


def _user_can_approve(user, approval):
    role_code = (approval.approver_role or "").upper()
    if user.has_role(role_code):
        return True
    return any(user.has_role(code) for code in ROLE_ALIASES.get(role_code, ()))


def _notify_staff(payslip, title, message, created_by=None):
    user = payslip.staff.user
    if not user:
        return None
    return Notification.objects.create(
        recipient=user,
        audience=Notification.STAFF,
        campus=payslip.staff.campus,
        title=title,
        message=message,
        priority=Notification.NORMAL,
        link=f"/teacher/payroll/payslips/{payslip.pk}/",
        created_by=created_by,
    )


def _append_note(payslip, text):
    stamp = timezone.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{stamp}] {text}"
    payslip.notes = f"{payslip.notes}\n{line}".strip() if payslip.notes else line


def _approval_queryset_for_user(user):
    qs = PayrollApproval.objects.select_related("payslip", "payslip__staff", "payslip__staff__campus", "approver").order_by("-created_at")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(payslip__staff__campus=scoped)
    if user.has_role(Role.ADMIN):
        return qs
    allowed = []
    for role, aliases in ROLE_ALIASES.items():
        if user.has_role(role) or any(user.has_role(code) for code in aliases):
            allowed.append(role)
    return qs.filter(approver_role__in=allowed)


@roles_required(*PAYROLL_REVIEW_ROLES)
def approval_dashboard(request):
    status = request.GET.get("status") or "pending"
    q = (request.GET.get("q") or "").strip()
    approvals = _approval_queryset_for_user(request.user)
    if status == "pending":
        approvals = approvals.filter(status=PayrollApproval.PENDING)
    elif status == "approved":
        approvals = approvals.filter(status=PayrollApproval.APPROVED)
    elif status == "rejected":
        approvals = approvals.filter(status=PayrollApproval.REJECTED)
    elif status == "paid":
        approvals = approvals.filter(payslip__status=Payslip.PAID)
    if q:
        approvals = approvals.filter(
            Q(payslip__staff__first_name__icontains=q)
            | Q(payslip__staff__last_name__icontains=q)
            | Q(payslip__staff__staff_id__icontains=q)
            | Q(approver_role__icontains=q)
        )
    scoped = get_user_campus_scope(request.user)
    count_approvals = PayrollApproval.objects.select_related("payslip", "payslip__staff")
    count_payslips = Payslip.objects.select_related("staff")
    if scoped:
        count_approvals = count_approvals.filter(payslip__staff__campus=scoped)
        count_payslips = count_payslips.filter(staff__campus=scoped)
    counts = {
        "pending": count_approvals.filter(status=PayrollApproval.PENDING).count(),
        "approved": count_approvals.filter(status=PayrollApproval.APPROVED).count(),
        "rejected": count_approvals.filter(status=PayrollApproval.REJECTED).count(),
        "paid": count_payslips.filter(status=Payslip.PAID).count(),
    }
    grouped = count_payslips.values("status").annotate(total=Count("id")).order_by("status")
    return render(request, "portals/admin/hr/payroll/approval_dashboard.html", {"approvals": approvals[:200], "counts": counts, "grouped": grouped, "status": status, "q": q})


@roles_required(*PAYROLL_REVIEW_ROLES)
def approval_detail(request, pk):
    approval = get_object_or_404(_approval_queryset_for_user(request.user), pk=pk)
    payslip = get_object_or_404(
        Payslip.objects.select_related("staff", "staff__campus", "generated_by", "approved_by").filter(pk=approval.payslip_id).prefetch_related("allowances__allowance_type", "deductions__deduction_type", "approvals__approver"),
        pk=approval.payslip_id,
    )
    can_act = approval.status == PayrollApproval.PENDING and payslip.status == Payslip.PENDING_APPROVAL and _user_can_approve(request.user, approval)
    return render(request, "portals/admin/hr/payroll/approval_detail.html", {"approval": approval, "payslip": payslip, "can_act": can_act})


@roles_required(*PAYROLL_REVIEW_ROLES)
@require_POST
def approval_action(request, pk):
    approval = get_object_or_404(_approval_queryset_for_user(request.user).select_related("payslip"), pk=pk)
    if not _user_can_approve(request.user, approval):
        return HttpResponseForbidden("You do not have the required approval role.")
    payslip = approval.payslip
    if payslip.status != Payslip.PENDING_APPROVAL or approval.status != PayrollApproval.PENDING:
        messages.error(request, "This approval item is no longer pending.")
        return redirect("admin_hr_payroll_approval_detail", pk=approval.pk)
    action = request.POST.get("action")
    comments = request.POST.get("comments") or ""
    with transaction.atomic():
        approval.approver = request.user
        approval.approved_at = timezone.now()
        approval.comments = comments
        if action == "reject":
            approval.status = PayrollApproval.REJECTED
            approval.save()
            payslip.status = Payslip.REJECTED
            _append_note(payslip, f"Rejected by {request.user.get_username()}: {comments}")
            payslip.save(update_fields=["status", "notes"])
            messages.success(request, "Payslip rejected.")
        else:
            approval.status = PayrollApproval.APPROVED
            approval.save()
            _append_note(payslip, f"Approved by {request.user.get_username()} as {approval.approver_role}: {comments}")
            if not payslip.approvals.filter(status=PayrollApproval.PENDING).exists():
                payslip.status = Payslip.APPROVED
                payslip.approved_by = request.user
                payslip.approved_at = timezone.now()
                payslip.save(update_fields=["status", "approved_by", "approved_at", "notes"])
                _notify_staff(payslip, "Payslip approved", f"Your {payslip.period_year}/{payslip.period_month:02d} payslip has been approved.", request.user)
            else:
                payslip.save(update_fields=["notes"])
            messages.success(request, "Payslip approved.")
    return redirect("admin_hr_payroll_approval_detail", pk=approval.pk)


@roles_required(*PAYROLL_REVIEW_ROLES)
@require_POST
def mark_paid(request, pk):
    payslip_qs = Payslip.objects.select_related("staff", "staff__campus")
    scoped = get_user_campus_scope(request.user)
    if scoped:
        payslip_qs = payslip_qs.filter(staff__campus=scoped)
    payslip = get_object_or_404(payslip_qs, pk=pk)
    if not request.user.has_role(Role.ADMIN):
        return HttpResponseForbidden("Only admin users can mark payroll as paid.")
    if payslip.status != Payslip.APPROVED:
        messages.error(request, "Only approved payslips can be marked as paid.")
        return redirect("admin_hr_payroll_payslip_detail", pk=payslip.pk)
    _append_note(payslip, f"Marked paid by {request.user.get_username()}: {request.POST.get('comments') or ''}")
    payslip.status = Payslip.PAID
    payslip.paid_at = timezone.now()
    payslip.save(update_fields=["status", "paid_at", "notes"])
    _notify_staff(payslip, "Payslip paid", f"Your {payslip.period_year}/{payslip.period_month:02d} payslip has been marked as paid.", request.user)
    messages.success(request, "Payslip marked as paid and staff notified.")
    return redirect("admin_hr_payroll_payslip_detail", pk=payslip.pk)


def _render_payslip_pdf(payslip):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 60
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Payslip")
    y -= 35
    pdf.setFont("Helvetica", 10)
    rows = [
        ("Staff", payslip.staff.get_full_name()),
        ("Staff ID", payslip.staff.staff_id or "-"),
        ("Period", f"{payslip.period_year}/{payslip.period_month:02d}"),
        ("Status", payslip.get_status_display()),
        ("Base salary", str(payslip.base_salary)),
        ("Allowances", str(payslip.total_allowances)),
        ("Deductions", str(payslip.total_deductions)),
        ("Gross salary", str(payslip.gross_salary)),
        ("Net salary", str(payslip.net_salary)),
    ]
    for label, value in rows:
        pdf.drawString(50, y, f"{label}:")
        pdf.drawString(170, y, value)
        y -= 22
    y -= 10
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Approval chain")
    y -= 22
    pdf.setFont("Helvetica", 9)
    for approval in payslip.approvals.all():
        pdf.drawString(50, y, f"{approval.approver_role}: {approval.get_status_display()} by {approval.approver or '-'} at {approval.approved_at or '-'}")
        y -= 18
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


@roles_required(*PAYROLL_REVIEW_ROLES)
def payslip_pdf(request, pk):
    payslip_qs = Payslip.objects.select_related("staff", "staff__campus").prefetch_related("approvals__approver")
    scoped = get_user_campus_scope(request.user)
    if scoped:
        payslip_qs = payslip_qs.filter(staff__campus=scoped)
    payslip = get_object_or_404(payslip_qs, pk=pk)
    buffer = _render_payslip_pdf(payslip)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="payslip_{payslip.staff.staff_id or payslip.staff_id}_{payslip.period_year}_{payslip.period_month:02d}.pdf"'
    return response
