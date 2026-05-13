"""
Teacher portal search: students the teacher teaches and their own grievances.
"""
from typing import Any, Dict, List
from urllib.parse import urlencode

from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from apps.tenant.academics.models import Enrollment
from apps.tenant.grievances.models import Grievance
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role


def _q(request):
    return (request.GET.get("q") or "").strip()


def _teacher_visible_student_ids(teacher: TeacherProfile) -> set:
    from_enrollment = Enrollment.objects.filter(
        offering__teacher=teacher,
        status=Enrollment.ACTIVE,
    ).values_list("student_id", flat=True)
    from_stream = StudentProfile.objects.filter(
        stream__class_teacher=teacher,
        is_active=True,
    ).values_list("id", flat=True)
    return set(from_enrollment) | set(from_stream)


def _attendance_href(teacher: TeacherProfile, student: StudentProfile) -> str:
    en = (
        Enrollment.objects.filter(
            student=student,
            offering__teacher=teacher,
            status=Enrollment.ACTIVE,
        )
        .order_by("-offering__term__year__name", "-offering__term__order", "-id")
        .first()
    )
    if en:
        q_param = (student.student_id or student.last_name or student.first_name or "").strip()
        params = {"offering": str(en.offering_id)}
        if q_param:
            params["q"] = q_param
        return reverse("teacher_attendance_take") + "?" + urlencode(params)
    return reverse("teacher_attendance_home")


@role_required(Role.TEACHER)
def teacher_search(request):
    query = _q(request)
    teacher = TeacherProfile.objects.filter(user=request.user).select_related("campus").first()

    student_rows: List[Dict[str, Any]] = []
    grievances: List[Grievance] = []

    if not teacher:
        return render(
            request,
            "portals/teacher/search.html",
            {
                "q": query,
                "student_rows": [],
                "grievances": [],
                "missing_profile": True,
            },
        )

    if len(query) >= 2:
        visible = _teacher_visible_student_ids(teacher)
        if visible:
            sq = (
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(student_id__icontains=query)
                | Q(email__icontains=query)
            )
            for student in (
                StudentProfile.objects.select_related("campus", "stream")
                .filter(pk__in=visible)
                .filter(sq)[:15]
            ):
                student_rows.append(
                    {
                        "student": student,
                        "attendance_href": _attendance_href(teacher, student),
                    }
                )

        gq = Q(subject__icontains=query) | Q(body__icontains=query)
        grievances = list(
            Grievance.objects.filter(submitted_by=request.user)
            .filter(gq)
            .order_by("-created_at")[:15]
        )

    return render(
        request,
        "portals/teacher/search.html",
        {
            "q": query,
            "student_rows": student_rows,
            "grievances": grievances,
            "missing_profile": False,
        },
    )
