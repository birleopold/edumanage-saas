from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.finance.clearance_gates import clearance_gate
from apps.tenant.finance.clearance_models import ClearancePolicy
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .grading_results import build_report_card, score_result
from .services import published_assessments_for_student, score_map_for_student


def _student_profile(request):
    return StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()


@role_required(Role.STUDENT)
def results_home(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    clearance_decision, gate_response = clearance_gate(
        request,
        student,
        ClearancePolicy.ASSESSMENT_RESULTS,
    )
    if gate_response is not None:
        return gate_response

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
            "clearance_decision": clearance_decision,
        },
    )


@role_required(Role.STUDENT)
def report_card(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")
    clearance_decision, gate_response = clearance_gate(
        request,
        student,
        ClearancePolicy.ASSESSMENT_REPORT,
    )
    if gate_response is not None:
        return gate_response
    return render(
        request,
        "portals/student/results/report_card.html",
        {
            "student": student,
            "report": build_report_card(student),
            "clearance_decision": clearance_decision,
        },
    )


@role_required(Role.STUDENT)
def report_card_print(request):
    student = _student_profile(request)
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")
    clearance_decision, gate_response = clearance_gate(
        request,
        student,
        ClearancePolicy.ASSESSMENT_REPORT,
    )
    if gate_response is not None:
        return gate_response
    return render(
        request,
        "portals/student/results/report_card_print.html",
        {
            "student": student,
            "report": build_report_card(student),
            "clearance_decision": clearance_decision,
        },
    )
