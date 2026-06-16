from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .services import build_report_card, published_assessments_for_student, score_map_for_student, score_result


def _student_profile(request):
    return StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()


@role_required(Role.STUDENT)
def results_home(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assessments = list(published_assessments_for_student(student))
    score_map = score_map_for_student(student, assessments)
    result_map = {assessment.id: score_result(assessment, score_map.get(assessment.id)) for assessment in assessments}
    report = build_report_card(student)

    return render(
        request,
        "portals/student/results/home.html",
        {
            "student": student,
            "assessments": assessments,
            "score_map": score_map,
            "result_map": result_map,
            "report": report,
        },
    )


@role_required(Role.STUDENT)
def report_card(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")
    return render(
        request,
        "portals/student/results/report_card.html",
        {"student": student, "report": build_report_card(student)},
    )


@role_required(Role.STUDENT)
def report_card_print(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")
    return render(
        request,
        "portals/student/results/report_card_print.html",
        {"student": student, "report": build_report_card(student)},
    )
