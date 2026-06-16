from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .services import active_periods, entries_for_student, timetable_matrix, weekday_choices


@role_required(Role.STUDENT)
def my_timetable(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus", "stream").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    entries = list(entries_for_student(student))
    periods = list(active_periods())

    return render(
        request,
        "portals/student/timetable/home.html",
        {
            "student": student,
            "entries": entries,
            "periods": periods,
            "weekdays": weekday_choices(),
            "matrix": timetable_matrix(entries, periods),
        },
    )
