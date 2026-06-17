from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

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
    link = ParentStudentLink.objects.filter(parent=parent, student_id=student_id).select_related("student", "student__campus").first()
    return link.student if link else None


@role_required(Role.PARENT)
def results(request):
    parent = _parent(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    links = ParentStudentLink.objects.filter(parent=parent).select_related("student", "student__campus").order_by("-is_primary", "student__last_name")
    children = []
    for link in links:
        student = link.student
        scores = list(ExamScore.objects.filter(student=student, paper__results_published=True).select_related("paper", "paper__exam", "paper__offering__course"))
        attempts = OnlineExamAttempt.objects.filter(student=student, paper__results_published=True).select_related("paper", "paper__exam", "paper__offering__course")
        children.append({"student": student, "scores": scores, "attempts": attempts})
    return render(request, "portals/parent/exams/results.html", {"parent": parent, "children": children})


@role_required(Role.PARENT)
def exam_attempt_detail(request, student_id: int, attempt_id: int):
    parent = _parent(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    student = _linked_student(parent, student_id)
    if not student:
        return HttpResponseForbidden("You are not linked to this student.")
    attempt = get_object_or_404(OnlineExamAttempt.objects.select_related("paper", "paper__exam", "paper__offering__course"), pk=attempt_id, student=student)
    if not results_visible_for_paper(attempt.paper):
        messages.info(request, "This result is not yet published.")
        return redirect("parent_exam_results")
    score = ExamScore.objects.filter(paper=attempt.paper, student=student).first()
    return render(request, "portals/parent/exams/attempt_detail.html", {"parent": parent, "student": student, "attempt": attempt, "rows": responses_with_questions(attempt), "score": score})


@role_required(Role.PARENT)
def exam_report_card_pdf(request, student_id: int, exam_id: int):
    parent = _parent(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    student = _linked_student(parent, student_id)
    if not student:
        return HttpResponseForbidden("You are not linked to this student.")
    exam = get_object_or_404(Exam, pk=exam_id)
    scores = list(ExamScore.objects.filter(student=student, paper__exam=exam, paper__results_published=True, paper__report_cards_enabled=True).select_related("paper", "paper__offering__course", "paper__exam"))
    if not scores:
        messages.error(request, "No published report card is available for this exam.")
        return redirect("parent_exam_results")
    buf = generate_exam_report_card_pdf(student=student, exam=exam, scores=scores, org=get_or_create_organization())
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="exam_report_card_{exam.id}_{student.student_id}.pdf"'
    return response
