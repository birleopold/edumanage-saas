from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import ExamPaper, ExamScore


@role_required(Role.STUDENT)
def results(request):
    student = StudentProfile.objects.filter(user=request.user).first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    offering_ids = list(
        Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list("offering_id", flat=True)
    )

    papers = (
        ExamPaper.objects.select_related(
            "exam",
            "exam__term",
            "exam__term__year",
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
        )
        .filter(offering_id__in=offering_ids, is_published=True)
        .order_by("exam__term__year__name", "exam__term__order", "exam__name", "offering__course__name")
    )

    if student.campus_id:
        papers = papers.filter(offering__campus_id=student.campus_id)

    scores = ExamScore.objects.filter(paper__in=papers, student=student)
    score_map = {s.paper_id: s for s in scores}

    return render(
        request,
        "portals/student/exams/results.html",
        {"student": student, "papers": papers, "score_map": score_map},
    )
