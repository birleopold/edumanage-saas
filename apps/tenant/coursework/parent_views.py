from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.tenant.academics.models import Enrollment
from apps.tenant.orgsettings.services import campus_queryset, selected_campus_id_from_request, update_current_campus_from_request
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import Assignment, AssignmentSubmission, LearningMaterial


@role_required(Role.PARENT)
def coursework_home(request):
    update_current_campus_from_request(request)

    parent = ParentProfile.objects.filter(user=request.user).first()
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

    links = list(
        ParentStudentLink.objects.filter(parent=parent)
        .select_related("student", "student__campus", "student__stream", "student__stream__class_group")
        .order_by("-is_primary", "student__last_name", "student__first_name")
    )

    if campus_id:
        links = [l for l in links if getattr(l.student, "campus_id", None) == campus_id]

    if selected_student_id:
        links = [l for l in links if getattr(l, "student_id", None) == selected_student_id]

    now = timezone.now()

    children = []
    for link in links:
        student = link.student
        offerings = Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE)
        offering_ids = list(offerings.values_list("offering_id", flat=True))
        class_group = getattr(student.stream, "class_group", None) if student.stream else None

        materials_qs = LearningMaterial.objects.filter(is_active=True, publish_at__lte=now)
        assignments_qs = Assignment.objects.filter(is_active=True, publish_at__lte=now)

        materials_qs = materials_qs.filter(Q(campus__isnull=True) | Q(campus=student.campus)).filter(
            Q(stream__isnull=True) | Q(stream=student.stream)
        ).filter(Q(class_group__isnull=True) | Q(class_group=class_group)).filter(
            Q(offering__isnull=True) | Q(offering_id__in=offering_ids)
        )

        assignments_qs = assignments_qs.filter(Q(campus__isnull=True) | Q(campus=student.campus)).filter(
            Q(stream__isnull=True) | Q(stream=student.stream)
        ).filter(Q(class_group__isnull=True) | Q(class_group=class_group)).filter(
            Q(offering__isnull=True) | Q(offering_id__in=offering_ids)
        )

        materials_qs = materials_qs.prefetch_related("attachments")
        assignments_qs = assignments_qs.prefetch_related("attachments")

        assignments = list(assignments_qs.order_by("-publish_at")[:30])
        submissions = {
            s.assignment_id: s
            for s in AssignmentSubmission.objects.filter(student=student, assignment_id__in=[a.id for a in assignments])
        }

        for a in assignments:
            a.submission = submissions.get(a.id)
            a.is_submitted = bool(a.submission and a.submission.submitted_at)

        children.append(
            {
                "link": link,
                "student": student,
                "materials": list(materials_qs.order_by("-publish_at")[:10]),
                "assignments": assignments,
            }
        )

    return render(
        request,
        "portals/parent/coursework/home.html",
        {
            "parent": parent,
            "children": children,
            "campuses": campuses,
            "selected_campus_id": campus_id,
            "selected_student_id": selected_student_id,
        },
    )


@role_required(Role.PARENT)
def assignment_detail(request, student_id: int, pk: int):
    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    link = ParentStudentLink.objects.filter(parent=parent, student_id=student_id).select_related("student").first()
    if not link:
        return HttpResponseForbidden("You are not linked to this student.")

    assignment = get_object_or_404(Assignment.objects.prefetch_related("attachments"), pk=pk, is_active=True)
    submission = (
        AssignmentSubmission.objects.filter(assignment=assignment, student=link.student)
        .prefetch_related("attachments")
        .first()
    )

    return render(
        request,
        "portals/parent/coursework/assignment_detail.html",
        {"parent": parent, "student": link.student, "assignment": assignment, "submission": submission},
    )
