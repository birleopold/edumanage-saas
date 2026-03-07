from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Assignment, AssignmentSubmission, AssignmentSubmissionAttachment, LearningMaterial


@role_required(Role.STUDENT)
def coursework_home(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    offerings = Enrollment.objects.select_related("offering").filter(student=student, status=Enrollment.ACTIVE)
    offering_ids = list(offerings.values_list("offering_id", flat=True))

    now = timezone.now()

    materials_qs = LearningMaterial.objects.select_related("class_group", "stream", "offering").filter(is_active=True, publish_at__lte=now)
    assignments_qs = Assignment.objects.select_related("class_group", "stream", "offering").filter(is_active=True, publish_at__lte=now)

    # Scope to student
    class_group = getattr(student.stream, "class_group", None) if student.stream else None
    materials_qs = materials_qs.filter(
        Q(campus__isnull=True) | Q(campus=student.campus),
    ).filter(
        Q(stream__isnull=True) | Q(stream=student.stream),
    ).filter(
        Q(class_group__isnull=True) | Q(class_group=class_group),
    ).filter(
        Q(offering__isnull=True) | Q(offering_id__in=offering_ids),
    )

    assignments_qs = assignments_qs.filter(
        Q(campus__isnull=True) | Q(campus=student.campus),
    ).filter(
        Q(stream__isnull=True) | Q(stream=student.stream),
    ).filter(
        Q(class_group__isnull=True) | Q(class_group=class_group),
    ).filter(
        Q(offering__isnull=True) | Q(offering_id__in=offering_ids),
    )

    materials = list(materials_qs.order_by("-publish_at")[:50])
    assignments = list(assignments_qs.order_by("-publish_at")[:50])

    submission_map = {
        s.assignment_id: s
        for s in AssignmentSubmission.objects.filter(student=student, assignment_id__in=[a.id for a in assignments])
    }

    for a in assignments:
        a.submission = submission_map.get(a.id)
        a.is_submitted = bool(a.submission and a.submission.submitted_at)

    return render(
        request,
        "portals/student/coursework/home.html",
        {"student": student, "materials": materials, "assignments": assignments},
    )


@role_required(Role.STUDENT)
def assignment_detail(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments"), pk=pk, is_active=True)

    submission = AssignmentSubmission.objects.filter(assignment=assignment, student=student).prefetch_related("attachments").first()

    return render(
        request,
        "portals/student/coursework/assignment_detail.html",
        {"student": student, "assignment": assignment, "submission": submission},
    )


@role_required(Role.STUDENT)
def assignment_submit(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments"), pk=pk, is_active=True)

    submission, _created = AssignmentSubmission.objects.get_or_create(assignment=assignment, student=student)

    # Policy B: only one submission
    if submission.submitted_at is not None:
        messages.error(request, "You have already submitted this assignment.")
        return redirect("student_coursework_assignment_detail", pk=assignment.pk)

    if request.method == "POST":
        text_answer = request.POST.get("text_answer") or ""
        files = request.FILES.getlist("files")

        if not text_answer and not files:
            messages.error(request, "Please enter an answer or attach a file.")
            return redirect("student_coursework_assignment_submit", pk=assignment.pk)

        submission.text_answer = text_answer
        submission.submitted_at = timezone.now()
        submission.save(update_fields=["text_answer", "submitted_at", "updated_at"])

        for f in files:
            AssignmentSubmissionAttachment.objects.create(submission=submission, file=f)

        messages.success(request, "Assignment submitted successfully.")
        return redirect("student_coursework_assignment_submitted", pk=assignment.pk)

    return render(
        request,
        "portals/student/coursework/assignment_submit.html",
        {"student": student, "assignment": assignment, "submission": submission},
    )


@role_required(Role.STUDENT)
def assignment_submitted(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments"), pk=pk, is_active=True)
    submission = (
        AssignmentSubmission.objects.filter(assignment=assignment, student=student)
        .prefetch_related("attachments")
        .first()
    )

    return render(
        request,
        "portals/student/coursework/assignment_submitted.html",
        {"student": student, "assignment": assignment, "submission": submission},
    )
