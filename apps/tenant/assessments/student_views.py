from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Assessment, AssessmentScore


@role_required(Role.STUDENT)
def results_home(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    enrollments = (
        Enrollment.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
        )
        .filter(student=student, status=Enrollment.ACTIVE)
        .order_by("offering__term__year__name", "offering__term__order", "offering__course__name")
    )

    offering_ids = list(enrollments.values_list("offering_id", flat=True))

    assessments = (
        Assessment.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
        )
        .filter(offering_id__in=offering_ids, is_published=True)
        .order_by("offering__term__year__name", "offering__term__order", "name")
    )

    scores = AssessmentScore.objects.filter(assessment__in=assessments, student=student)
    score_map = {s.assessment_id: s for s in scores}

    return render(
        request,
        "portals/student/results/home.html",
        {
            "student": student,
            "enrollments": enrollments,
            "assessments": assessments,
            "score_map": score_map,
        },
    )
