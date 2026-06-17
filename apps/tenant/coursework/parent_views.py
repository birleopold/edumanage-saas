from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.tenant.orgsettings.services import campus_queryset, selected_campus_id_from_request, update_current_campus_from_request
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import Assignment, AssignmentSubmission, LearningMaterial
from .services import (
    attach_material_progress,
    attach_submission_status,
    learner_progress_summary,
    student_can_access_assignment,
    student_can_access_material,
    visible_assignments_for_student,
    visible_materials_for_student,
)


def _parent_profile(request):
    return ParentProfile.objects.filter(user=request.user).first()


def _linked_student_or_forbidden(parent, student_id: int):
    link = ParentStudentLink.objects.filter(parent=parent, student_id=student_id).select_related("student", "student__campus", "student__stream", "student__stream__class_group").first()
    return link.student if link else None


@role_required(Role.PARENT)
def coursework_home(request):
    update_current_campus_from_request(request)
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    selected_student_id_raw = (request.GET.get("student") or "").strip()
    selected_student_id = None
    if selected_student_id_raw:
        try:
            selected_student_id = int(selected_student_id_raw)
        except (TypeError, ValueError):
            selected_student_id = None
    campus_id = selected_campus_id_from_request(request)
    campuses = campus_queryset()
    links = list(ParentStudentLink.objects.filter(parent=parent).select_related("student", "student__campus", "student__stream", "student__stream__class_group").order_by("-is_primary", "student__last_name", "student__first_name"))
    if campus_id:
        links = [link for link in links if getattr(link.student, "campus_id", None) == campus_id]
    if selected_student_id:
        links = [link for link in links if getattr(link, "student_id", None) == selected_student_id]
    children = []
    for link in links:
        student = link.student
        materials = list(visible_materials_for_student(student).order_by("-publish_at")[:10])
        assignments = list(visible_assignments_for_student(student).order_by("-publish_at")[:30])
        attach_material_progress(materials, student)
        attach_submission_status(assignments, student)
        summary = learner_progress_summary(student)
        children.append(
            {
                "link": link,
                "student": student,
                "materials": materials,
                "assignments": assignments,
                "summary": summary,
                "pending_count": sum(1 for assignment in assignments if not assignment.is_submitted),
                "submitted_count": sum(1 for assignment in assignments if assignment.is_submitted),
                "overdue_count": sum(1 for assignment in assignments if assignment.is_overdue and not assignment.is_submitted),
                "marked_count": sum(1 for assignment in assignments if assignment.is_marked),
            }
        )
    return render(request, "portals/parent/coursework/home.html", {"parent": parent, "children": children, "campuses": campuses, "selected_campus_id": campus_id, "selected_student_id": selected_student_id, "now": timezone.now()})


@role_required(Role.PARENT)
def material_detail(request, student_id: int, pk: int):
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    student = _linked_student_or_forbidden(parent, student_id)
    if not student:
        return HttpResponseForbidden("You are not linked to this student.")
    material = get_object_or_404(LearningMaterial.objects.prefetch_related("attachments", "comments", "comments__user", "progress_records"), pk=pk, is_active=True)
    if not student_can_access_material(student, material):
        return HttpResponseForbidden("This material is not assigned to your child.")
    progress = material.progress_records.filter(student=student).first()
    return render(request, "portals/parent/coursework/material_detail.html", {"parent": parent, "student": student, "material": material, "progress": progress})


@role_required(Role.PARENT)
def assignment_detail(request, student_id: int, pk: int):
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    student = _linked_student_or_forbidden(parent, student_id)
    if not student:
        return HttpResponseForbidden("You are not linked to this student.")
    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments", "comments", "comments__user", "progress_records"), pk=pk, is_active=True)
    if not student_can_access_assignment(student, assignment):
        return HttpResponseForbidden("This assignment is not assigned to your child.")
    submission = AssignmentSubmission.objects.filter(assignment=assignment, student=student).prefetch_related("attachments").first()
    progress = assignment.progress_records.filter(student=student).first()
    return render(request, "portals/parent/coursework/assignment_detail.html", {"parent": parent, "student": student, "assignment": assignment, "submission": submission, "progress": progress})
