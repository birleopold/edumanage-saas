from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .forms import CourseworkCommentForm
from .models import Assignment, AssignmentSubmission, AssignmentSubmissionAttachment, CourseworkComment, LearningMaterial
from .services import (
    assignment_is_overdue,
    attach_material_progress,
    attach_submission_status,
    learner_progress_summary,
    mark_assignment_submitted,
    mark_assignment_viewed,
    mark_material_completed,
    mark_material_viewed,
    student_can_access_assignment,
    student_can_access_material,
    visible_assignments_for_student,
    visible_materials_for_student,
)


def _student_profile(request):
    return StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()


@role_required(Role.STUDENT)
def coursework_home(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    materials = list(visible_materials_for_student(student).order_by("-publish_at")[:50])
    assignments = list(visible_assignments_for_student(student).order_by("-publish_at")[:50])
    attach_material_progress(materials, student)
    attach_submission_status(assignments, student)
    summary = learner_progress_summary(student)

    pending_count = sum(1 for assignment in assignments if not assignment.is_submitted)
    submitted_count = sum(1 for assignment in assignments if assignment.is_submitted)
    overdue_count = sum(1 for assignment in assignments if assignment.is_overdue and not assignment.is_submitted)
    marked_count = sum(1 for assignment in assignments if assignment.is_marked)

    return render(
        request,
        "portals/student/coursework/home.html",
        {
            "student": student,
            "materials": materials,
            "assignments": assignments,
            "summary": summary,
            "pending_count": pending_count,
            "submitted_count": submitted_count,
            "overdue_count": overdue_count,
            "marked_count": marked_count,
        },
    )


@role_required(Role.STUDENT)
def material_detail(request, pk: int):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    material = get_object_or_404(LearningMaterial.objects.prefetch_related("attachments", "comments", "comments__user"), pk=pk, is_active=True)
    if not student_can_access_material(student, material):
        return HttpResponseForbidden("This material is not assigned to you.")

    progress = mark_material_viewed(student, material)

    if request.method == "POST" and material.allow_comments:
        form = CourseworkCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.material = material
            comment.user = request.user
            comment.save()
            messages.success(request, "Comment added.")
            return redirect("student_coursework_material_detail", pk=material.pk)
    else:
        form = CourseworkCommentForm()

    return render(
        request,
        "portals/student/coursework/material_detail.html",
        {"student": student, "material": material, "progress": progress, "comment_form": form},
    )


@role_required(Role.STUDENT)
def material_complete(request, pk: int):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")
    material = get_object_or_404(LearningMaterial, pk=pk, is_active=True)
    if not student_can_access_material(student, material):
        return HttpResponseForbidden("This material is not assigned to you.")
    if request.method == "POST":
        mark_material_completed(student, material)
        messages.success(request, "Material marked as completed.")
    return redirect("student_coursework_material_detail", pk=material.pk)


@role_required(Role.STUDENT)
def assignment_detail(request, pk: int):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments", "comments", "comments__user"), pk=pk, is_active=True)
    if not student_can_access_assignment(student, assignment):
        return HttpResponseForbidden("This assignment is not assigned to you.")

    progress = mark_assignment_viewed(student, assignment)
    submission = AssignmentSubmission.objects.filter(assignment=assignment, student=student).prefetch_related("attachments").first()
    is_overdue = assignment_is_overdue(assignment)

    if request.method == "POST" and assignment.allow_comments:
        form = CourseworkCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.assignment = assignment
            comment.user = request.user
            comment.save()
            messages.success(request, "Comment added.")
            return redirect("student_coursework_assignment_detail", pk=assignment.pk)
    else:
        form = CourseworkCommentForm()

    return render(
        request,
        "portals/student/coursework/assignment_detail.html",
        {
            "student": student,
            "assignment": assignment,
            "submission": submission,
            "is_overdue": is_overdue,
            "progress": progress,
            "comment_form": form,
        },
    )


@role_required(Role.STUDENT)
def assignment_submit(request, pk: int):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments"), pk=pk, is_active=True)
    if not student_can_access_assignment(student, assignment):
        return HttpResponseForbidden("This assignment is not assigned to you.")

    submission, _created = AssignmentSubmission.objects.get_or_create(assignment=assignment, student=student)
    if submission.submitted_at is not None:
        messages.error(request, "You have already submitted this assignment.")
        return redirect("student_coursework_assignment_detail", pk=assignment.pk)
    if assignment_is_overdue(assignment):
        messages.error(request, "The submission deadline has passed. Please contact your teacher.")
        return redirect("student_coursework_assignment_detail", pk=assignment.pk)

    if request.method == "POST":
        text_answer = request.POST.get("text_answer") or ""
        files = request.FILES.getlist("files")
        if not text_answer.strip() and not files:
            messages.error(request, "Please enter an answer or attach a file.")
            return redirect("student_coursework_assignment_submit", pk=assignment.pk)
        submission.text_answer = text_answer
        submission.submitted_at = timezone.now()
        submission.save(update_fields=["text_answer", "submitted_at", "updated_at"])
        for uploaded in files:
            AssignmentSubmissionAttachment.objects.create(submission=submission, file=uploaded)
        mark_assignment_submitted(student, assignment)
        messages.success(request, "Assignment submitted successfully.")
        return redirect("student_coursework_assignment_submitted", pk=assignment.pk)

    return render(request, "portals/student/coursework/assignment_submit.html", {"student": student, "assignment": assignment, "submission": submission})


@role_required(Role.STUDENT)
def assignment_submitted(request, pk: int):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")
    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments"), pk=pk, is_active=True)
    if not student_can_access_assignment(student, assignment):
        return HttpResponseForbidden("This assignment is not assigned to you.")
    submission = AssignmentSubmission.objects.filter(assignment=assignment, student=student).prefetch_related("attachments").first()
    return render(request, "portals/student/coursework/assignment_submitted.html", {"student": student, "assignment": assignment, "submission": submission})
