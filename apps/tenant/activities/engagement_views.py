from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.parents.models import ParentStudentLink
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import roles_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role

from .engagement_forms import ActivityIncidentForm
from .engagement_models import ActivityCertificate
from .engagement_services import (
    certificate_pdf,
    issue_activity_certificate,
    learner_activity_summary,
)
from .programme_models import ActivityAchievement


STAFF_ROLES = (Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL, Role.TEACHER)


def _student_for_user(request, student_id=None):
    user = request.user
    if user.is_superuser or any(user.has_role(code) for code in STAFF_ROLES):
        qs = StudentProfile.objects.filter(is_active=True)
        campus = get_user_campus_scope(user)
        if campus:
            qs = qs.filter(campus=campus)
        return get_object_or_404(qs, pk=student_id) if student_id else qs.first()
    if user.has_role(Role.STUDENT):
        student = StudentProfile.objects.filter(user=user, is_active=True).first()
        if student_id and student and student.pk != student_id:
            return None
        return student
    if user.has_role(Role.PARENT):
        qs = StudentProfile.objects.filter(
            parentstudentlink__parent__user=user,
            is_active=True,
        ).distinct()
        return get_object_or_404(qs, pk=student_id) if student_id else qs.first()
    return None


@login_required
def learner_activity_dashboard(request, student_id=None):
    student = _student_for_user(request, student_id)
    if not student:
        return HttpResponseForbidden(
            "No authorised learner activity record is available for this account."
        )
    children = []
    if request.user.has_role(Role.PARENT):
        children = list(
            StudentProfile.objects.filter(
                parentstudentlink__parent__user=request.user,
                is_active=True,
            ).order_by("last_name", "first_name")
        )
    return render(
        request,
        "portals/activities/learner_dashboard.html",
        {
            "base_template": base_template_for(request.user),
            "student": student,
            "summary": learner_activity_summary(student),
            "children": children,
            "can_manage": bool(
                request.user.is_superuser
                or any(request.user.has_role(code) for code in STAFF_ROLES)
            ),
        },
    )


@roles_required(*STAFF_ROLES)
def incident_create(request):
    campus = get_user_campus_scope(request.user)
    form = ActivityIncidentForm(
        request.POST or None,
        campus=campus,
    )
    if request.method == "POST" and form.is_valid():
        incident = form.save(commit=False)
        incident.recorded_by = request.user
        if incident.status in {incident.RESOLVED, incident.CLOSED}:
            incident.resolved_by = request.user
        incident.full_clean()
        incident.save()
        messages.success(request, "Activity incident recorded.")
        return redirect(
            "activities_learner_dashboard_for_student",
            student_id=incident.student_id,
        )
    return render(
        request,
        "portals/activities/incident_form.html",
        {
            "base_template": base_template_for(request.user),
            "form": form,
        },
    )


@roles_required(*STAFF_ROLES)
def certificate_issue(request, achievement_id):
    achievement = get_object_or_404(
        ActivityAchievement.objects.select_related(
            "membership",
            "membership__student",
            "membership__activity",
        ),
        pk=achievement_id,
    )
    campus = get_user_campus_scope(request.user)
    if campus and achievement.membership.student.campus_id != campus.pk:
        return HttpResponseForbidden("The learner belongs to another campus.")
    certificate = issue_activity_certificate(
        achievement,
        issued_by=request.user,
    )
    messages.success(request, "Verifiable activity certificate issued.")
    return redirect("activities_certificate_pdf", pk=certificate.pk)


@login_required
def certificate_download(request, pk):
    certificate = get_object_or_404(
        ActivityCertificate.objects.select_related(
            "achievement",
            "achievement__membership",
            "achievement__membership__student",
            "achievement__membership__activity",
        ),
        pk=pk,
    )
    student = certificate.achievement.membership.student
    if not _student_for_user(request, student.pk):
        return HttpResponseForbidden("You do not have access to this certificate.")
    verify_url = request.build_absolute_uri(
        reverse(
            "activities_certificate_verify",
            args=[certificate.verification_token],
        )
    )
    response = FileResponse(
        certificate_pdf(certificate, verify_url),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = (
        f'inline; filename="{certificate.reference}.pdf"'
    )
    return response


def verify_certificate(request, token):
    certificate = get_object_or_404(
        ActivityCertificate.objects.select_related(
            "achievement",
            "achievement__membership",
            "achievement__membership__student",
            "achievement__membership__activity",
        ),
        verification_token=token,
    )
    return render(
        request,
        "portals/activities/certificate_verify.html",
        {
            "certificate": certificate,
            "valid": certificate.is_valid,
        },
    )
