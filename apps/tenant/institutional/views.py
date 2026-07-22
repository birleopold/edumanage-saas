from __future__ import annotations

from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.parents.models import ParentStudentLink
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import roles_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role

from .forms import (
    CandidateDossierForm,
    CandidateExamAttendanceForm,
    CandidateMockCycleForm,
    ECDObservationForm,
    LearnerSubjectCombinationForm,
    MealAttendanceForm,
    MealServiceForm,
    PermitForm,
    ReportTemplateForm,
    ResultPolicyForm,
    StudentPropertyForm,
    VisitationWindowForm,
    VisitorRecordForm,
)
from .models import (
    CandidateDossier,
    CandidateExamAttendance,
    CandidateMockCycle,
    ECDObservation,
    LearnerSubjectCombination,
    MealAttendance,
    MealService,
    ReportTemplate,
    ResultPolicy,
    StudentProperty,
    VerifiablePermit,
    VisitationWindow,
    VisitorRecord,
)
from .services import academic_summary, permit_pdf, report_pdf, transcript_pdf


ADMIN_ROLES = (Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL)

RESOURCE_MAP = {
    "report-templates": (ReportTemplate, ReportTemplateForm, "Report templates"),
    "result-policies": (ResultPolicy, ResultPolicyForm, "Result policies"),
    "ecd-observations": (ECDObservation, ECDObservationForm, "ECD observations"),
    "subject-combinations": (LearnerSubjectCombination, LearnerSubjectCombinationForm, "Learner subject combinations"),
    "candidate-dossiers": (CandidateDossier, CandidateDossierForm, "Candidate dossiers"),
    "mock-cycles": (CandidateMockCycle, CandidateMockCycleForm, "Mock examination cycles"),
    "exam-attendance": (CandidateExamAttendance, CandidateExamAttendanceForm, "Candidate examination attendance"),
    "permits": (VerifiablePermit, PermitForm, "Verifiable permits"),
    "visitation-windows": (VisitationWindow, VisitationWindowForm, "Visitation windows"),
    "visitors": (VisitorRecord, VisitorRecordForm, "Visitor records"),
    "meal-services": (MealService, MealServiceForm, "Meal services"),
    "meal-attendance": (MealAttendance, MealAttendanceForm, "Meal attendance"),
    "student-property": (StudentProperty, StudentPropertyForm, "Student property"),
}


def _scoped_queryset(request, model):
    qs = model.objects.all()
    campus = get_user_campus_scope(request.user)
    if campus is None:
        return qs
    if model in {ReportTemplate, ResultPolicy, VisitationWindow, MealService}:
        return qs.filter(campus=campus)
    if model in {ECDObservation, LearnerSubjectCombination, CandidateDossier, VerifiablePermit, VisitorRecord, MealAttendance, StudentProperty}:
        lookup = {
            ECDObservation: "student__campus",
            LearnerSubjectCombination: "student__campus",
            CandidateDossier: "student__campus",
            VerifiablePermit: "student__campus",
            VisitorRecord: "student__campus",
            MealAttendance: "student__campus",
            StudentProperty: "student__campus",
        }[model]
        return qs.filter(**{lookup: campus})
    if model in {CandidateMockCycle, CandidateExamAttendance}:
        return qs.filter(dossier__student__campus=campus)
    return qs


def _apply_form_scope(request, form):
    campus = get_user_campus_scope(request.user)
    if not campus:
        return form
    for name in ("campus",):
        if name in form.fields:
            form.fields[name].queryset = form.fields[name].queryset.filter(pk=campus.pk)
            form.fields[name].initial = campus
    if "student" in form.fields:
        form.fields["student"].queryset = StudentProfile.objects.filter(campus=campus, is_active=True)
    if "dossier" in form.fields:
        form.fields["dossier"].queryset = CandidateDossier.objects.filter(student__campus=campus)
    if "service" in form.fields:
        form.fields["service"].queryset = MealService.objects.filter(campus=campus)
    if "visitation_window" in form.fields:
        form.fields["visitation_window"].queryset = VisitationWindow.objects.filter(campus=campus)
    return form


def _stamp_actor(obj, user):
    for name in ("recorded_by", "registered_by", "verified_by", "marked_by", "approved_by", "received_by"):
        if hasattr(obj, f"{name}_id") and not getattr(obj, f"{name}_id"):
            setattr(obj, name, user)
    if isinstance(obj, CandidateDossier) and obj.registration_status in {CandidateDossier.READY, CandidateDossier.SUBMITTED, CandidateDossier.APPROVED}:
        obj.verified_by = user
        obj.verified_at = timezone.now()


@roles_required(*ADMIN_ROLES)
def dashboard(request):
    campus = get_user_campus_scope(request.user)
    student_filter = {"student__campus": campus} if campus else {}
    metrics = [
        ("Active report templates", ReportTemplate.objects.filter(is_active=True, **({"campus": campus} if campus else {})).count()),
        ("Result policies", ResultPolicy.objects.filter(is_active=True, **({"campus": campus} if campus else {})).count()),
        ("Candidate dossiers", CandidateDossier.objects.filter(**student_filter).count()),
        ("Valid permits", VerifiablePermit.objects.filter(status=VerifiablePermit.ACTIVE, **student_filter).count()),
        ("Visitor records", VisitorRecord.objects.filter(**student_filter).count()),
        ("Meal attendance records", MealAttendance.objects.filter(**student_filter).count()),
        ("Property records", StudentProperty.objects.filter(**student_filter).count()),
    ]
    resources = [{"key": key, "title": title, "count": _scoped_queryset(request, model).count()} for key, (model, _, title) in RESOURCE_MAP.items()]
    return render(request, "portals/institutional/dashboard.html", {"metrics": metrics, "resources": resources})


@roles_required(*ADMIN_ROLES)
def resource_list(request, resource):
    if resource not in RESOURCE_MAP:
        raise Http404
    model, _, title = RESOURCE_MAP[resource]
    objects = _scoped_queryset(request, model).order_by("-pk")[:250]
    return render(request, "portals/institutional/resource_list.html", {"resource": resource, "title": title, "objects": objects})


@roles_required(*ADMIN_ROLES)
def resource_form(request, resource, pk=None):
    if resource not in RESOURCE_MAP:
        raise Http404
    model, form_class, title = RESOURCE_MAP[resource]
    obj = get_object_or_404(_scoped_queryset(request, model), pk=pk) if pk else None
    form = _apply_form_scope(request, form_class(request.POST or None, request.FILES or None, instance=obj))
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            _stamp_actor(saved, request.user)
            saved.full_clean()
            saved.save()
            if hasattr(form, "save_m2m"):
                form.save_m2m()
        messages.success(request, f"{title.rstrip('s')} saved successfully.")
        return redirect("institutional_resource_list", resource=resource)
    return render(request, "portals/institutional/resource_form.html", {"resource": resource, "title": title, "form": form, "object": obj})


def _student_for_user(request, student_id=None):
    if request.user.is_superuser or any(request.user.has_role(code) for code in ADMIN_ROLES):
        qs = StudentProfile.objects.filter(is_active=True)
        campus = get_user_campus_scope(request.user)
        if campus:
            qs = qs.filter(campus=campus)
        return get_object_or_404(qs, pk=student_id) if student_id else None
    if request.user.has_role(Role.STUDENT):
        student = StudentProfile.objects.filter(user=request.user, is_active=True).first()
        if student_id and student and student.pk != student_id:
            return None
        return student
    if request.user.has_role(Role.PARENT):
        qs = StudentProfile.objects.filter(parentstudentlink__parent__user=request.user, is_active=True).distinct()
        return get_object_or_404(qs, pk=student_id) if student_id else qs.first()
    if request.user.has_role(Role.TEACHER):
        qs = StudentProfile.objects.filter(is_active=True)
        teacher = getattr(request.user, "teacher_profile", None)
        if teacher and teacher.campus_id:
            qs = qs.filter(campus_id=teacher.campus_id)
        return get_object_or_404(qs, pk=student_id) if student_id else None
    return None


@login_required
def my_records(request, student_id=None):
    student = _student_for_user(request, student_id)
    if not student:
        return HttpResponseForbidden("No authorised learner record is available for this account.")
    context = {
        "base_template": base_template_for(request.user),
        "student": student,
        "summary": academic_summary(student),
        "dossiers": CandidateDossier.objects.filter(student=student).select_related("external_session"),
        "permits": VerifiablePermit.objects.filter(student=student).order_by("-issued_at"),
        "visitors": VisitorRecord.objects.filter(student=student).order_by("-arrived_at")[:25],
        "meals": MealAttendance.objects.filter(student=student).select_related("service").order_by("-service__service_date")[:50],
        "property_records": StudentProperty.objects.filter(student=student).order_by("-received_at"),
        "combinations": LearnerSubjectCombination.objects.filter(student=student).select_related("combination", "academic_year"),
    }
    return render(request, "portals/institutional/my_records.html", context)


@roles_required(Role.TEACHER, *ADMIN_ROLES)
def teacher_observations(request, student_id=None):
    student = _student_for_user(request, student_id) if student_id else None
    form = ECDObservationForm(request.POST or None, initial={"student": student} if student else None)
    if request.user.has_role(Role.TEACHER) and not request.user.is_superuser:
        teacher = getattr(request.user, "teacher_profile", None)
        if teacher and teacher.campus_id:
            form.fields["student"].queryset = StudentProfile.objects.filter(campus_id=teacher.campus_id, is_active=True)
    if request.method == "POST" and form.is_valid():
        observation = form.save(commit=False)
        observation.recorded_by = request.user
        observation.full_clean()
        observation.save()
        messages.success(request, "Developmental observation saved.")
        return redirect("institutional_teacher_observations")
    observations = ECDObservation.objects.select_related("student", "academic_term").order_by("-observed_on")[:100]
    return render(request, "portals/institutional/teacher_observations.html", {"base_template": base_template_for(request.user), "form": form, "observations": observations})


def _ensure_document_permit(student, permit_type, title, reference_prefix, user):
    reference = f"{reference_prefix}-{student.pk}"
    permit, _ = VerifiablePermit.objects.get_or_create(
        reference=reference,
        defaults={"permit_type": permit_type, "student": student, "title": title, "approved_by": user, "metadata": {"generated_from": "institutional_document"}},
    )
    if permit.student_id != student.pk or permit.permit_type != permit_type:
        raise Http404
    return permit


def _can_view_student(request, student):
    resolved = _student_for_user(request, student.pk)
    return bool(resolved and resolved.pk == student.pk)


@login_required
def permit_download(request, pk):
    permit = get_object_or_404(VerifiablePermit.objects.select_related("student"), pk=pk)
    if not _can_view_student(request, permit.student):
        return HttpResponseForbidden("You do not have access to this permit.")
    verify_url = request.build_absolute_uri(reverse("institutional_verify", args=[permit.verification_token]))
    response = FileResponse(permit_pdf(permit, verify_url), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{permit.reference}.pdf"'
    return response


@login_required
def transcript_download(request, student_id):
    student = get_object_or_404(StudentProfile, pk=student_id)
    if not _can_view_student(request, student):
        return HttpResponseForbidden("You do not have access to this transcript.")
    permit = _ensure_document_permit(student, VerifiablePermit.TRANSCRIPT, "Academic Transcript", "TRANSCRIPT", request.user)
    verify_url = request.build_absolute_uri(reverse("institutional_verify", args=[permit.verification_token]))
    response = FileResponse(transcript_pdf(student, verify_url), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="transcript-{student.student_id or student.pk}.pdf"'
    return response


@login_required
def report_download(request, student_id):
    student = get_object_or_404(StudentProfile, pk=student_id)
    if not _can_view_student(request, student):
        return HttpResponseForbidden("You do not have access to this report.")
    permit = _ensure_document_permit(student, VerifiablePermit.REPORT, "Learner Progress Report", "REPORT", request.user)
    verify_url = request.build_absolute_uri(reverse("institutional_verify", args=[permit.verification_token]))
    response = FileResponse(report_pdf(student, verify_url), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="report-{student.student_id or student.pk}.pdf"'
    return response


def verify_document(request, token):
    permit = get_object_or_404(VerifiablePermit.objects.select_related("student"), verification_token=token)
    return render(request, "portals/institutional/verify.html", {"permit": permit, "valid": permit.is_valid})


@roles_required(*ADMIN_ROLES)
@require_POST
def revoke_permit(request, pk):
    permit = get_object_or_404(_scoped_queryset(request, VerifiablePermit), pk=pk)
    permit.status = VerifiablePermit.REVOKED
    permit.save(update_fields=("status",))
    messages.success(request, "Permit revoked. Its verification page now reports it as invalid.")
    return redirect("institutional_resource_list", resource="permits")
