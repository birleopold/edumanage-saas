from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .services import active_periods, entries_for_teacher, timetable_matrix, weekday_choices


@role_required(Role.TEACHER)
def my_timetable(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    entries = list(entries_for_teacher(teacher))
    periods = list(active_periods())
    matrix = timetable_matrix(entries, periods)

    return render(
        request,
        "portals/teacher/timetable/home.html",
        {
            "teacher": teacher,
            "entries": entries,
            "periods": periods,
            "weekdays": weekday_choices(),
            "matrix": matrix,
        },
    )
