from collections import defaultdict

from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .models import TimetableEntry


@role_required(Role.TEACHER)
def my_timetable(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    entries = (
        TimetableEntry.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
            "offering__class_group",
            "period",
            "room",
        )
        .filter(is_active=True, offering__teacher=teacher)
        .order_by("weekday", "period__order", "period__name")
    )

    by_day = defaultdict(list)
    for e in entries:
        by_day[e.weekday].append(e)

    return render(
        request,
        "portals/teacher/timetable/home.html",
        {"teacher": teacher, "entries": entries, "by_day": dict(by_day)},
    )
