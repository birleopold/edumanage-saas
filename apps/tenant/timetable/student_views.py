from collections import defaultdict

from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import TimetableEntry


@role_required(Role.STUDENT)
def my_timetable(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    offering_ids = list(
        Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list(
            "offering_id", flat=True
        )
    )

    entries = (
        TimetableEntry.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
            "offering__class_group",
            "offering__teacher",
            "period",
            "room",
        )
        .filter(is_active=True, offering_id__in=offering_ids)
        .order_by("weekday", "period__order", "period__name")
    )

    by_day = defaultdict(list)
    for e in entries:
        by_day[e.weekday].append(e)

    return render(
        request,
        "portals/student/timetable/home.html",
        {"student": student, "entries": entries, "by_day": dict(by_day)},
    )
