from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.orgsettings.services import campus_queryset, selected_campus_id_from_request, update_current_campus_from_request
from apps.tenant.parents.models import ParentProfile
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import AttendanceEntry
from .services import (
    parent_can_view_student,
    parent_linked_students,
    student_attendance_entries,
    student_attendance_summary,
)


def _parent_profile(request):
    return ParentProfile.objects.filter(user=request.user).first()


@role_required(Role.PARENT)
def attendance_home(request):
    update_current_campus_from_request(request)
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    campus_id = selected_campus_id_from_request(request)
    students_qs = parent_linked_students(parent)
    if campus_id:
        students_qs = students_qs.filter(campus_id=campus_id)

    children = []
    for student in students_qs:
        recent_entries = list(student_attendance_entries(student)[:8])
        children.append(
            {
                "student": student,
                "summary": student_attendance_summary(student),
                "recent_entries": recent_entries,
            }
        )

    return render(
        request,
        "portals/parent/attendance/home.html",
        {
            "parent": parent,
            "children": children,
            "campuses": campus_queryset(),
            "selected_campus_id": campus_id,
        },
    )


@role_required(Role.PARENT)
def student_attendance_detail(request, student_id: int):
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    if not parent_can_view_student(parent, student_id):
        return HttpResponseForbidden("You are not linked to this student.")

    student = get_object_or_404(StudentProfile.objects.select_related("campus", "stream", "stream__class_group"), pk=student_id)
    status = (request.GET.get("status") or "").strip().upper()
    q = (request.GET.get("q") or "").strip()
    page_number = request.GET.get("page") or 1

    entries_qs = student_attendance_entries(student)
    if status in {choice[0] for choice in AttendanceEntry.STATUS_CHOICES}:
        entries_qs = entries_qs.filter(status=status)
    if q:
        entries_qs = entries_qs.filter(session__offering__course__name__icontains=q)

    paginator = Paginator(entries_qs, 30)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/parent/attendance/student_detail.html",
        {
            "parent": parent,
            "student": student,
            "entries": page_obj.object_list,
            "page_obj": page_obj,
            "summary": student_attendance_summary(student),
            "status": status,
            "q": q,
            "STATUS_CHOICES": AttendanceEntry.STATUS_CHOICES,
        },
    )
