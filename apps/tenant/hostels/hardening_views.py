from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import admin_portal_required, role_required
from apps.tenant.users.models import Role

from .hardening_forms import GuardianContactLogForm, WelfareCaseEscalationForm
from .hardening_models import GuardianContactLog, WelfareCaseEscalation
from .hardening_services import (
    escalate_welfare_case,
    phase7_operational_readiness,
    reconcile_roll_call_leave_statuses,
    record_guardian_contact,
    student_boarding_readiness,
)
from .models import BoardingProfile, HostelRollCall
from .welfare_views import _case_queryset_for, _leave_queryset_for, _student_queryset_for


def _save_guardian_contact(*, form, student, recorded_by, **source_kwargs):
    cleaned = dict(form.cleaned_data)
    parent = cleaned.pop("parent", None)
    log = record_guardian_contact(
        student=student,
        recorded_by=recorded_by,
        **source_kwargs,
        **cleaned,
    )
    if parent is not None:
        log.parent = parent
        log.full_clean()
        log.save(update_fields=["parent"])
    return log


@role_required(Role.ADMIN)
def operational_hardening_dashboard(request):
    readiness = phase7_operational_readiness()
    students = list(_student_queryset_for(request.user).filter(is_active=True).order_by("last_name", "first_name"))
    readiness_rows = [
        {"student": student, "readiness": student_boarding_readiness(student)}
        for student in students
    ]
    incomplete_rows = [row for row in readiness_rows if not row["readiness"]["ready"]]
    recent_contacts = GuardianContactLog.objects.select_related(
        "student", "parent", "recorded_by", "boarding_leave", "welfare_case", "roll_call_entry"
    )[:15]
    recent_escalations = WelfareCaseEscalation.objects.select_related(
        "welfare_case", "welfare_case__student", "escalated_by"
    ).exclude(level=WelfareCaseEscalation.NONE)[:15]
    return render(
        request,
        "portals/admin/hostels/welfare/hardening_dashboard.html",
        {
            "readiness": readiness,
            "incomplete_rows": incomplete_rows[:50],
            "incomplete_student_count": len(incomplete_rows),
            "recent_contacts": recent_contacts,
            "recent_escalations": recent_escalations,
        },
    )


@admin_portal_required
def boarding_leave_contact_create(request, pk):
    leave = get_object_or_404(_leave_queryset_for(request.user), pk=pk)
    if request.method == "POST":
        form = GuardianContactLogForm(request.POST, student=leave.student)
        if form.is_valid():
            try:
                _save_guardian_contact(
                    form=form,
                    student=leave.student,
                    boarding_leave=leave,
                    recorded_by=request.user,
                )
                messages.success(request, "Guardian contact recorded for this leave.")
                return redirect("admin_boarding_leave_detail", pk=leave.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = GuardianContactLogForm(
            student=leave.student,
            default_name=leave.guardian_name,
            default_phone=leave.guardian_phone,
            default_purpose=GuardianContactLog.LEAVE_APPROVAL,
        )
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {
            "form": form,
            "title": f"Record guardian contact — {leave.student}",
            "back_url_name": "admin_boarding_leave_detail",
            "back_url_pk": leave.pk,
        },
    )


@admin_portal_required
def welfare_case_contact_create(request, pk):
    case = get_object_or_404(_case_queryset_for(request.user), pk=pk)
    profile = BoardingProfile.objects.filter(student=case.student).first()
    if request.method == "POST":
        form = GuardianContactLogForm(request.POST, student=case.student)
        if form.is_valid():
            try:
                _save_guardian_contact(
                    form=form,
                    student=case.student,
                    welfare_case=case,
                    recorded_by=request.user,
                )
                messages.success(request, "Guardian contact recorded for this welfare case.")
                return redirect("admin_welfare_case_detail", pk=case.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = GuardianContactLogForm(
            student=case.student,
            default_name=profile.primary_guardian_name if profile else "",
            default_phone=profile.primary_guardian_phone if profile else "",
            default_purpose=GuardianContactLog.WELFARE,
        )
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {
            "form": form,
            "title": f"Record guardian contact — {case.student}",
            "back_url_name": "admin_welfare_case_detail",
            "back_url_pk": case.pk,
        },
    )


@admin_portal_required
def welfare_case_escalate(request, pk):
    case = get_object_or_404(_case_queryset_for(request.user), pk=pk)
    escalation = WelfareCaseEscalation.objects.filter(welfare_case=case).first()
    if request.method == "POST":
        form = WelfareCaseEscalationForm(request.POST, instance=escalation)
        if form.is_valid():
            try:
                escalate_welfare_case(
                    case,
                    user=request.user,
                    **form.cleaned_data,
                )
                messages.success(request, "Welfare-case escalation updated.")
                return redirect("admin_welfare_case_detail", pk=case.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = WelfareCaseEscalationForm(instance=escalation)
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {
            "form": form,
            "title": f"Escalate welfare case — {case.student}",
            "back_url_name": "admin_welfare_case_detail",
            "back_url_pk": case.pk,
        },
    )


@admin_portal_required
def hostel_roll_call_reconcile(request, pk):
    if request.method != "POST":
        raise Http404
    roll_call = get_object_or_404(HostelRollCall, pk=pk)
    try:
        summary = reconcile_roll_call_leave_statuses(roll_call, dry_run=False)
        messages.success(
            request,
            "Roll-call leave status reconciled: "
            f"{summary['set_on_leave_count']} marked on leave; "
            f"{summary['reset_to_unmarked_count']} reset to unmarked; "
            f"{summary['preserved_explicit_count']} explicit decisions preserved.",
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("admin_hostel_roll_call_detail", pk=roll_call.pk)
