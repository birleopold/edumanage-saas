from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.academics.models import CourseOffering
from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .forms import AssignmentForm, LearningMaterialForm
from .models import (
    Assignment,
    AssignmentAttachment,
    AssignmentSubmission,
    LearningMaterial,
    LearningMaterialAttachment,
)
from .services import ensure_assignment_submission_rows, submission_summary_for_assignment


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _teacher_profile(request):
    teacher = TeacherProfile.objects.filter(user=request.user).select_related("campus").first()
    if not teacher:
        return None
    return teacher


def _teacher_offerings(teacher):
    return CourseOffering.objects.select_related("course", "term", "term__year", "class_group").filter(teacher=teacher)


def _can_manage_assignment(teacher, assignment: Assignment, user) -> bool:
    if assignment.offering_id:
        return assignment.offering and assignment.offering.teacher_id == teacher.id
    return assignment.created_by_id == user.id


def _can_manage_material(teacher, material: LearningMaterial, user) -> bool:
    if material.offering_id:
        return material.offering and material.offering.teacher_id == teacher.id
    return material.created_by_id == user.id


def _add_material_attachments(material: LearningMaterial, files) -> int:
    created = 0
    for uploaded in files or []:
        LearningMaterialAttachment.objects.create(material=material, file=uploaded)
        created += 1
    return created


def _add_assignment_attachments(assignment: Assignment, files) -> int:
    created = 0
    for uploaded in files or []:
        AssignmentAttachment.objects.create(assignment=assignment, file=uploaded)
        created += 1
    return created


def _configure_teacher_form(form, offerings):
    if "offering" in form.fields:
        form.fields["offering"].queryset = offerings
    return form


@role_required(Role.TEACHER)
def coursework_home(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    offerings = _teacher_offerings(teacher)
    assignments_qs = Assignment.objects.select_related("offering", "class_group", "stream").prefetch_related("attachments").filter(
        Q(offering__in=offerings) | Q(offering__isnull=True, created_by=request.user)
    )
    materials_qs = LearningMaterial.objects.select_related("offering", "class_group", "stream").prefetch_related("attachments").filter(
        Q(offering__in=offerings) | Q(offering__isnull=True, created_by=request.user)
    )

    if q:
        assignments_qs = assignments_qs.filter(Q(title__icontains=q) | Q(instructions__icontains=q))
        materials_qs = materials_qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    assignments_page = Paginator(assignments_qs.order_by("-publish_at"), per_page).get_page(page_number)
    materials = list(materials_qs.order_by("-publish_at")[:20])

    assignments = list(assignments_page.object_list)
    for assignment in assignments:
        ensure_assignment_submission_rows(assignment)
        assignment.summary = submission_summary_for_assignment(assignment)

    return render(
        request,
        "portals/teacher/coursework/home.html",
        {
            "teacher": teacher,
            "offerings": offerings,
            "materials": materials,
            "assignments": assignments,
            "page_obj": assignments_page,
            "q": q,
            "per_page": per_page,
        },
    )


@role_required(Role.TEACHER)
def material_create(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    offerings = _teacher_offerings(teacher)

    if request.method == "POST":
        form = _configure_teacher_form(LearningMaterialForm(request.POST, request.FILES), offerings)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.offering_id and obj.offering_id not in set(offerings.values_list("id", flat=True)):
                return HttpResponseForbidden("You are not allowed to create material for this offering.")
            obj.created_by = request.user
            obj.save()
            uploaded_count = _add_material_attachments(obj, form.cleaned_data.get("attachments"))
            messages.success(
                request,
                "Material created" + (f" with {uploaded_count} attachment(s)" if uploaded_count else "") + ".",
            )
            return redirect("teacher_coursework_material_detail", pk=obj.pk)
    else:
        form = _configure_teacher_form(LearningMaterialForm(), offerings)

    return render(request, "portals/teacher/coursework/material_form.html", {"form": form, "mode": "create"})


@role_required(Role.TEACHER)
def material_detail(request, pk: int):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    material = get_object_or_404(
        LearningMaterial.objects.select_related("offering", "class_group", "stream").prefetch_related("attachments"),
        pk=pk,
    )
    if not _can_manage_material(teacher, material, request.user):
        return HttpResponseForbidden("You are not allowed to view this material.")

    return render(
        request,
        "portals/teacher/coursework/material_detail.html",
        {"teacher": teacher, "material": material},
    )


@role_required(Role.TEACHER)
def material_edit(request, pk: int):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    material = get_object_or_404(LearningMaterial.objects.select_related("offering").prefetch_related("attachments"), pk=pk)
    if not _can_manage_material(teacher, material, request.user):
        return HttpResponseForbidden("You are not allowed to edit this material.")

    offerings = _teacher_offerings(teacher)
    if request.method == "POST":
        form = _configure_teacher_form(LearningMaterialForm(request.POST, request.FILES, instance=material), offerings)
        if form.is_valid():
            obj = form.save()
            uploaded_count = _add_material_attachments(obj, form.cleaned_data.get("attachments"))
            messages.success(
                request,
                "Material updated" + (f" and {uploaded_count} attachment(s) added" if uploaded_count else "") + ".",
            )
            return redirect("teacher_coursework_material_detail", pk=obj.pk)
    else:
        form = _configure_teacher_form(LearningMaterialForm(instance=material), offerings)

    return render(
        request,
        "portals/teacher/coursework/material_form.html",
        {"form": form, "mode": "edit", "material": material},
    )


@role_required(Role.TEACHER)
def assignment_create(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    offerings = _teacher_offerings(teacher)

    if request.method == "POST":
        form = _configure_teacher_form(AssignmentForm(request.POST, request.FILES), offerings)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.offering_id and obj.offering_id not in set(offerings.values_list("id", flat=True)):
                return HttpResponseForbidden("You are not allowed to create an assignment for this offering.")
            obj.created_by = request.user
            obj.save()
            uploaded_count = _add_assignment_attachments(obj, form.cleaned_data.get("attachments"))
            created_rows = ensure_assignment_submission_rows(obj)
            details = []
            if uploaded_count:
                details.append(f"{uploaded_count} attachment(s)")
            if created_rows:
                details.append(f"{created_rows} student submission row(s)")
            messages.success(request, "Assignment created" + (" with " + ", ".join(details) if details else "") + ".")
            return redirect("teacher_coursework_assignment_detail", pk=obj.pk)
    else:
        form = _configure_teacher_form(AssignmentForm(), offerings)

    return render(request, "portals/teacher/coursework/assignment_form.html", {"form": form, "mode": "create"})


@role_required(Role.TEACHER)
def assignment_detail(request, pk: int):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    assignment = get_object_or_404(
        Assignment.objects.select_related("offering", "class_group", "stream").prefetch_related("attachments"),
        pk=pk,
    )
    if not _can_manage_assignment(teacher, assignment, request.user):
        return HttpResponseForbidden("You are not allowed to view this assignment.")

    ensure_assignment_submission_rows(assignment)
    return render(
        request,
        "portals/teacher/coursework/assignment_detail.html",
        {
            "teacher": teacher,
            "assignment": assignment,
            "summary": submission_summary_for_assignment(assignment),
            "now": timezone.now(),
        },
    )


@role_required(Role.TEACHER)
def assignment_edit(request, pk: int):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.select_related("offering").prefetch_related("attachments"), pk=pk)
    if not _can_manage_assignment(teacher, assignment, request.user):
        return HttpResponseForbidden("You are not allowed to edit this assignment.")

    offerings = _teacher_offerings(teacher)
    if request.method == "POST":
        form = _configure_teacher_form(AssignmentForm(request.POST, request.FILES, instance=assignment), offerings)
        if form.is_valid():
            obj = form.save()
            uploaded_count = _add_assignment_attachments(obj, form.cleaned_data.get("attachments"))
            created_rows = ensure_assignment_submission_rows(obj)
            details = []
            if uploaded_count:
                details.append(f"{uploaded_count} attachment(s) added")
            if created_rows:
                details.append(f"{created_rows} student submission row(s) created")
            messages.success(request, "Assignment updated" + ("; " + "; ".join(details) if details else "") + ".")
            return redirect("teacher_coursework_assignment_detail", pk=obj.pk)
    else:
        form = _configure_teacher_form(AssignmentForm(instance=assignment), offerings)

    return render(
        request,
        "portals/teacher/coursework/assignment_form.html",
        {"form": form, "mode": "edit", "assignment": assignment},
    )


@role_required(Role.TEACHER)
def assignment_submissions(request, pk: int):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.select_related("offering", "offering__teacher"), pk=pk)
    if not _can_manage_assignment(teacher, assignment, request.user):
        return HttpResponseForbidden("You are not allowed to view submissions for this assignment.")

    ensure_assignment_submission_rows(assignment)

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()

    subs_qs = AssignmentSubmission.objects.select_related("student").prefetch_related("attachments").filter(assignment=assignment)
    if q:
        subs_qs = subs_qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
        )
    if status == "submitted":
        subs_qs = subs_qs.filter(submitted_at__isnull=False)
    elif status == "pending":
        subs_qs = subs_qs.filter(submitted_at__isnull=True)
    elif status == "marked":
        subs_qs = subs_qs.filter(marked_at__isnull=False)

    subs = list(subs_qs.order_by("student__last_name", "student__first_name"))
    for submission in subs:
        submission.is_submitted = submission.submitted_at is not None
        submission.is_marked = submission.marked_at is not None

    return render(
        request,
        "portals/teacher/coursework/submissions.html",
        {
            "teacher": teacher,
            "assignment": assignment,
            "submissions": subs,
            "summary": submission_summary_for_assignment(assignment),
            "q": q,
            "status": status,
        },
    )


@role_required(Role.TEACHER)
def submission_mark(request, assignment_id: int, submission_id: int):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.select_related("offering", "offering__teacher"), pk=assignment_id)
    if not _can_manage_assignment(teacher, assignment, request.user):
        return HttpResponseForbidden("You are not allowed to mark this assignment.")

    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related("student").prefetch_related("attachments"),
        pk=submission_id,
        assignment=assignment,
    )

    if request.method == "POST":
        score_raw = request.POST.get("score")
        feedback = request.POST.get("feedback") or ""

        score = None
        if score_raw not in (None, ""):
            try:
                score = Decimal(str(score_raw))
            except (InvalidOperation, ValueError):
                messages.error(request, "Invalid score.")
                return redirect("teacher_coursework_submission_mark", assignment_id=assignment.pk, submission_id=submission.pk)
            if score < 0:
                messages.error(request, "Score cannot be negative.")
                return redirect("teacher_coursework_submission_mark", assignment_id=assignment.pk, submission_id=submission.pk)
            if assignment.max_score is not None and score > assignment.max_score:
                messages.error(request, "Score cannot exceed the assignment maximum score.")
                return redirect("teacher_coursework_submission_mark", assignment_id=assignment.pk, submission_id=submission.pk)

        submission.score = score
        submission.feedback = feedback
        submission.marked_by = request.user
        submission.marked_at = timezone.now()
        submission.save(update_fields=["score", "feedback", "marked_by", "marked_at", "updated_at"])
        messages.success(request, "Submission marked.")
        return redirect("teacher_coursework_assignment_submissions", pk=assignment.pk)

    return render(
        request,
        "portals/teacher/coursework/mark.html",
        {"teacher": teacher, "assignment": assignment, "submission": submission},
    )
