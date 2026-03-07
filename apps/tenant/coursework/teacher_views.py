from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .forms import AssignmentForm, LearningMaterialForm
from .models import Assignment, AssignmentSubmission


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.TEACHER)
def coursework_home(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    offerings = CourseOffering.objects.select_related("course", "term", "term__year", "class_group").filter(teacher=teacher)

    assignments_qs = Assignment.objects.select_related("offering", "class_group", "stream").filter(offering__in=offerings)
    if q:
        assignments_qs = assignments_qs.filter(Q(title__icontains=q) | Q(instructions__icontains=q))

    paginator = Paginator(assignments_qs.order_by("-publish_at"), per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/teacher/coursework/home.html",
        {
            "teacher": teacher,
            "offerings": offerings,
            "assignments": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@role_required(Role.TEACHER)
def material_create(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    offerings = CourseOffering.objects.filter(teacher=teacher)

    if request.method == "POST":
        form = LearningMaterialForm(request.POST)
        form.fields["offering"].queryset = offerings
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.publish_at and obj.publish_at > timezone.now():
                pass
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Material created.")
            return redirect("teacher_coursework_home")
    else:
        form = LearningMaterialForm()
        form.fields["offering"].queryset = offerings

    return render(request, "portals/teacher/coursework/material_form.html", {"form": form})


@role_required(Role.TEACHER)
def assignment_create(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    offerings = CourseOffering.objects.filter(teacher=teacher)

    if request.method == "POST":
        form = AssignmentForm(request.POST)
        form.fields["offering"].queryset = offerings
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.offering_id and obj.offering_id not in offerings.values_list("id", flat=True):
                return HttpResponseForbidden("You are not allowed to create an assignment for this offering.")
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Assignment created.")
            return redirect("teacher_coursework_home")
    else:
        form = AssignmentForm()
        form.fields["offering"].queryset = offerings

    return render(request, "portals/teacher/coursework/assignment_form.html", {"form": form})


@role_required(Role.TEACHER)
def assignment_submissions(request, pk: int):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.select_related("offering", "offering__teacher"), pk=pk)
    if assignment.offering and assignment.offering.teacher_id != teacher.id:
        return HttpResponseForbidden("You are not allowed to view submissions for this assignment.")

    # Ensure placeholder submission rows exist for all enrolled students.
    if assignment.offering_id:
        enrollment_student_ids = list(
            Enrollment.objects.filter(offering_id=assignment.offering_id, status=Enrollment.ACTIVE).values_list(
                "student_id", flat=True
            )
        )
        if enrollment_student_ids:
            existing_student_ids = set(
                AssignmentSubmission.objects.filter(assignment=assignment, student_id__in=enrollment_student_ids).values_list(
                    "student_id", flat=True
                )
            )
            missing_ids = [sid for sid in enrollment_student_ids if sid not in existing_student_ids]
            if missing_ids:
                with transaction.atomic():
                    AssignmentSubmission.objects.bulk_create(
                        [AssignmentSubmission(assignment=assignment, student_id=sid) for sid in missing_ids],
                        ignore_conflicts=True,
                    )

    q = (request.GET.get("q") or "").strip()

    subs_qs = AssignmentSubmission.objects.select_related("student").filter(assignment=assignment)
    if q:
        subs_qs = subs_qs.filter(
            Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q) | Q(student__student_id__icontains=q)
        )

    subs = list(subs_qs.order_by("student__last_name", "student__first_name"))
    # enrich with status
    for s in subs:
        s.is_submitted = s.submitted_at is not None

    return render(
        request,
        "portals/teacher/coursework/submissions.html",
        {"teacher": teacher, "assignment": assignment, "submissions": subs, "q": q},
    )


@role_required(Role.TEACHER)
def submission_mark(request, assignment_id: int, submission_id: int):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.select_related("offering", "offering__teacher"), pk=assignment_id)
    if assignment.offering and assignment.offering.teacher_id != teacher.id:
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
                score = float(score_raw)
            except ValueError:
                messages.error(request, "Invalid score.")
                return redirect("teacher_coursework_assignment_submissions", pk=assignment.pk)

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
