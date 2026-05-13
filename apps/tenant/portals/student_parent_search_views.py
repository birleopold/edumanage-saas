"""
Scoped search for student and parent portals (announcements, coursework, documents, finance, children).
"""
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.tenant.academics.models import Enrollment
from apps.tenant.announcements.models import Announcement
from apps.tenant.coursework.models import Assignment, LearningMaterial
from apps.tenant.documents.models import Document
from apps.tenant.finance.models import Invoice
from apps.tenant.grievances.models import Grievance
from apps.tenant.orgsettings.services import (
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role


def _q(request) -> str:
    return (request.GET.get("q") or "").strip()


def _coursework_visibility(student: StudentProfile, now):
    """Match visibility rules used on student/parent coursework home pages."""
    offerings = Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE)
    offering_ids = list(offerings.values_list("offering_id", flat=True))
    class_group = getattr(student.stream, "class_group", None) if student.stream else None

    materials = LearningMaterial.objects.filter(is_active=True, publish_at__lte=now)
    assignments = Assignment.objects.filter(is_active=True, publish_at__lte=now)

    def _scope(qs):
        return (
            qs.filter(Q(campus__isnull=True) | Q(campus=student.campus))
            .filter(Q(stream__isnull=True) | Q(stream=student.stream))
            .filter(Q(class_group__isnull=True) | Q(class_group=class_group))
            .filter(Q(offering__isnull=True) | Q(offering_id__in=offering_ids))
        )

    return _scope(materials), _scope(assignments)


@role_required(Role.STUDENT)
def student_search(request):
    query = _q(request)
    student = StudentProfile.objects.filter(user=request.user).select_related(
        "campus", "stream", "stream__class_group"
    ).first()

    announcements: List[Announcement] = []
    assignments: List[Assignment] = []
    materials: List[LearningMaterial] = []
    documents: List[Document] = []
    invoices: List[Invoice] = []

    if not student:
        return render(
            request,
            "portals/student/search.html",
            {
                "q": query,
                "missing_profile": True,
                "announcements": [],
                "assignments": [],
                "materials": [],
                "documents": [],
                "invoices": [],
            },
        )

    if len(query) >= 2:
        aq = Q(title__icontains=query) | Q(body__icontains=query)
        announcements = list(
            Announcement.objects.filter(is_active=True)
            .filter(Q(audience=Announcement.ALL) | Q(audience=Announcement.STUDENTS))
            .filter(aq)[:15]
        )

        now = timezone.now()
        materials_qs, assignments_qs = _coursework_visibility(student, now)
        cq = Q(title__icontains=query) | Q(instructions__icontains=query)
        assignments = list(assignments_qs.filter(cq).order_by("-publish_at")[:15])
        mq = Q(title__icontains=query) | Q(description__icontains=query)
        materials = list(materials_qs.filter(mq).order_by("-publish_at")[:12])

        dq = Q(title__icontains=query) | Q(description__icontains=query)
        documents = list(
            Document.objects.filter(is_active=True)
            .filter(Q(audience=Document.ALL) | Q(audience=Document.STUDENTS))
            .filter(dq)[:15]
        )

        iq = Q(reference__icontains=query)
        invoices = list(
            Invoice.objects.filter(student=student)
            .filter(iq)
            .select_related("student")
            .order_by("-created_at")[:15]
        )

    return render(
        request,
        "portals/student/search.html",
        {
            "q": query,
            "missing_profile": False,
            "student": student,
            "announcements": announcements,
            "assignments": assignments,
            "materials": materials,
            "documents": documents,
            "invoices": invoices,
            "coursework_home_url": reverse("student_coursework_home"),
        },
    )


def _parent_links(request) -> Tuple[Optional[ParentProfile], List[ParentStudentLink]]:
    update_current_campus_from_request(request)
    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return None, []
    campus_id = selected_campus_id_from_request(request)
    qs = (
        ParentStudentLink.objects.filter(parent=parent)
        .select_related("student", "student__campus", "student__stream", "student__stream__class_group")
        .order_by("-is_primary", "student__last_name", "student__first_name")
    )
    if campus_id:
        qs = qs.filter(student__campus_id=campus_id)
    return parent, list(qs)


@role_required(Role.PARENT)
def parent_search(request):
    query = _q(request)
    parent, links = _parent_links(request)

    matched_children: List[Dict[str, Any]] = []
    announcements: List[Announcement] = []
    assignment_rows: List[Dict[str, Any]] = []
    documents: List[Document] = []
    invoices: List[Invoice] = []
    grievances: List[Grievance] = []

    if not parent:
        return render(
            request,
            "portals/parent/search.html",
            {
                "q": query,
                "missing_profile": True,
                "matched_children": [],
                "announcements": [],
                "assignment_rows": [],
                "documents": [],
                "invoices": [],
                "grievances": [],
            },
        )

    if len(query) >= 2:
        child_ids = [link.student_id for link in links]
        lq = (
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(student_id__icontains=query)
        )
        matching_ids = set(
            StudentProfile.objects.filter(pk__in=child_ids)
            .filter(lq)
            .values_list("pk", flat=True)
        )
        for link in links:
            if link.student_id in matching_ids:
                matched_children.append(
                    {
                        "student": link.student,
                        "coursework_url": reverse("parent_coursework_home")
                        + f"?student={link.student_id}",
                    }
                )

        aq = Q(title__icontains=query) | Q(body__icontains=query)
        announcements = list(
            Announcement.objects.filter(is_active=True)
            .filter(Q(audience=Announcement.ALL) | Q(audience=Announcement.PARENTS))
            .filter(aq)[:15]
        )

        now = timezone.now()
        cq = Q(title__icontains=query) | Q(instructions__icontains=query)
        for link in links:
            _, assignments_qs = _coursework_visibility(link.student, now)
            for a in assignments_qs.filter(cq).order_by("-publish_at")[:5]:
                assignment_rows.append(
                    {
                        "student": link.student,
                        "assignment": a,
                        "href": reverse(
                            "parent_coursework_assignment_detail",
                            kwargs={"student_id": link.student_id, "pk": a.pk},
                        ),
                    }
                )
        assignment_rows = assignment_rows[:18]

        dq = Q(title__icontains=query) | Q(description__icontains=query)
        documents = list(
            Document.objects.filter(is_active=True)
            .filter(Q(audience=Document.ALL) | Q(audience=Document.PARENTS))
            .filter(dq)[:15]
        )

        student_ids = [link.student_id for link in links]
        if student_ids:
            iq = Q(reference__icontains=query)
            invoices = list(
                Invoice.objects.filter(student_id__in=student_ids)
                .filter(iq)
                .select_related("student")
                .order_by("-created_at")[:15]
            )

        gq = Q(subject__icontains=query) | Q(body__icontains=query)
        grievances = list(
            Grievance.objects.filter(submitted_by=request.user)
            .filter(gq)
            .order_by("-created_at")[:15]
        )

    return render(
        request,
        "portals/parent/search.html",
        {
            "q": query,
            "missing_profile": False,
            "matched_children": matched_children,
            "announcements": announcements,
            "assignment_rows": assignment_rows,
            "documents": documents,
            "invoices": invoices,
            "grievances": grievances,
        },
    )
