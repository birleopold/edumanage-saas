from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import AttendanceEntry
from .services import student_attendance_entries, student_attendance_summary


def _student_profile(request):
    return StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()


@role_required(Role.STUDENT)
def attendance_home(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

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
        "portals/student/attendance/home.html",
        {
            "student": student,
            "entries": page_obj.object_list,
            "page_obj": page_obj,
            "summary": student_attendance_summary(student),
            "status": status,
            "q": q,
            "STATUS_CHOICES": AttendanceEntry.STATUS_CHOICES,
        },
    )
