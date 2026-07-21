from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.finance.clearance_gates import clearance_gate
from apps.tenant.finance.clearance_models import ClearancePolicy
from apps.tenant.finance.clearance_services import evaluate_clearance
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Exam, ExamScore, OnlineExamAttempt
from .services import responses_with_questions, results_visible_for_paper
from .utils import generate_exam_report_card_pdf


def _parent(request):
    return ParentProfile.objects.filter(user=request.user).first()


def _linked_student(parent, student_id):
    link = ParentStudentLink.objects.filter(parent=parent, student_id=student_id).select_related("student", "student__campus", "student__stream", "student__stream__class_group").first()
    return link.student if link else None


@role_required(Role.PARENT)
def results(request):
    parent = _parent(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    links = ParentStudentLink.objects.filter(parent=parent).select_related("student", "student__campus", "student__stream", "student__stream__class_group").order_by("-is_primary", "student__last_name")
    children = []
    for link in links:
        student = link.student
        clearance_decision = evaluate_clearance(student, ClearancePolicy.EXAM_RESULTS)
        scores = []
        attempts = OnlineExamAttempt.objects.none()
        if clearance_decision.allowed:
            scores = list(ExamScore.objects.filter(student=student, paper__results_published=True).select_related("paper", "paper__exam", "paper__offering__course"))
            attempts = OnlineExamAttempt.objects.filter(student=student, paper__results_published=True).select_related("paper", "paper__exam", "paper__offering__course")
        children.append({"student": student, "scores": scores, "attempts": attempts, "clearance_decision": clearance_decision})
    return render(request, "portals/parent/exams/results.html", {"parent": parent, "children": children})


@role_required(Role.PARENT)
def exam_attempt_detail(request, student_id: int, attempt_id: int):
    parent = _parent(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    student = _linked_student(parent, student_id)
    if not student:
        return HttpResponseForbidden("You are not linked to this student.")
    attempt = get_object_or_404(OnlineExamAttempt.objects.select_related("paper", "paper__exam", "paper__exam__term", "paper__offering__course"), pk=attempt_id, student=student)
    clearance_decision, gate_response = clearance_gate(
        request,
        student,
        ClearancePolicy.EXAM_RESULTS,
        academic_term=attempt.paper.exam.term,
    )
    if gate_response is not None:
        return gate_response
    if not results_visible_for_paper(attempt.paper):
        messages.info(request, "This result is not yet published.")
        return redirect("parent_exam_results")
    score = ExamScore.objects.filter(paper=attempt.paper, student=student).first()
    return render(request, "portals/parent/exams/attempt_detail.html", {"parent": parent, "student": student, "attempt": attempt, "rows": responses_with_questions(attempt), "score": score, "clearance_decision": clearance_decision})


@role_required(Role.PARENT)
def exam_report_card_pdf(request, student_id: int, exam_id: int):
    parent = _parent(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    student = _linked_student(parent, student_id)
    if not student:
        return HttpResponseForbidden("You are not linked to this student.")
    exam = get_object_or_404(Exam.objects.select_related("term"), pk=exam_id)
    clearance_decision, gate_response = clearance_gate(
        request,
        student,
        ClearancePolicy.EXAM_REPORT,
        academic_term=exam.term,
    )
    if gate_response is not None:
        return gate_response
    scores = list(ExamScore.objects.filter(student=student, paper__exam=exam, paper__results_published=True, paper__report_cards_enabled=True).select_related("paper", "paper__offering__course", "paper__exam"))
    if not scores:
        messages.error(request, "No published report card is available for this exam.")
        return redirect("parent_exam_results")
    buf = generate_exam_report_card_pdf(student=student, exam=exam, scores=scores, org=get_or_create_organization())
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="exam_report_card_{exam.id}_{student.student_id}.pdf"'
    return response
