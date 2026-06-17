from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.academics.models import Enrollment
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Exam, ExamPaper, ExamScore, OnlineExamAttempt, SeatAllocation
from .services import (
    ordered_questions_for_attempt,
    paper_is_online_available,
    responses_with_questions,
    results_visible_for_paper,
    save_attempt_responses,
    start_or_get_attempt,
    student_is_allowed_for_paper,
    submit_attempt,
)
from .utils import generate_exam_report_card_pdf


def _get_student_profile(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus", "stream", "stream__class_group").first()
    if not student:
        raise HttpResponseForbidden("No student profile linked to this account.")
    return student


def _student_offering_ids(student):
    return list(Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list("offering_id", flat=True))


def _student_papers(student):
    qs = ExamPaper.objects.select_related("exam", "exam__term", "exam__term__year", "offering", "offering__course", "offering__class_group").filter(offering_id__in=_student_offering_ids(student), is_published=True)
    if student.campus_id:
        qs = qs.filter(offering__campus_id=student.campus_id)
    return qs


@role_required(Role.STUDENT)
def exam_dashboard(request):
    student = _get_student_profile(request)
    papers = list(_student_papers(student).order_by("-exam__start_date", "offering__course__name"))
    attempts = {a.paper_id: a for a in OnlineExamAttempt.objects.filter(student=student, paper__in=papers).select_related("paper")}
    visible_papers = [p for p in papers if results_visible_for_paper(p)]
    scores = ExamScore.objects.filter(student=student, paper__in=visible_papers).select_related("paper", "paper__exam", "paper__offering__course")
    score_map = {score.paper_id: score for score in scores}
    rows = []
    online_count = 0
    completed_count = 0
    for paper in papers:
        attempt = attempts.get(paper.id)
        score = score_map.get(paper.id)
        if paper.exam.exam_mode in [Exam.ONLINE, Exam.HYBRID]:
            online_count += 1
        if attempt and attempt.status in [OnlineExamAttempt.SUBMITTED, OnlineExamAttempt.AUTO_SUBMITTED, OnlineExamAttempt.GRADED]:
            completed_count += 1
        rows.append({"paper": paper, "attempt": attempt, "score": score, "results_visible": results_visible_for_paper(paper)})
    return render(request, "portals/student/exams/dashboard.html", {"student": student, "rows": rows, "online_count": online_count, "completed_count": completed_count, "scores": scores})


@role_required(Role.STUDENT)
def results(request):
    student = _get_student_profile(request)
    papers = _student_papers(student).filter(results_published=True).order_by("exam__term__year__name", "exam__term__order", "exam__name", "offering__course__name")
    scores = ExamScore.objects.filter(paper__in=papers, student=student).select_related("paper", "paper__exam", "paper__offering__course")
    score_map = {s.paper_id: s for s in scores}
    return render(request, "portals/student/exams/results.html", {"student": student, "papers": papers, "score_map": score_map, "scores": scores})


@role_required(Role.STUDENT)
def my_schedules(request):
    student = _get_student_profile(request)
    allocations = SeatAllocation.objects.filter(student=student).select_related("schedule__paper__exam", "schedule__paper__offering__course", "schedule__invigilator").order_by("schedule__date", "schedule__start_time")
    return render(request, "portals/student/exams/my_schedules.html", {"student": student, "allocations": allocations})


@role_required(Role.STUDENT)
def start_exam(request, pk: int):
    student = _get_student_profile(request)
    paper = get_object_or_404(ExamPaper.objects.select_related("exam", "offering", "offering__course").prefetch_related("questions__question"), pk=pk, is_published=True)
    if not student_is_allowed_for_paper(student, paper):
        return HttpResponseForbidden("You are not enrolled in this exam paper.")
    if not paper_is_online_available(paper):
        messages.error(request, "This paper is not available online.")
        return redirect("student_exams_dashboard")
    attempt = OnlineExamAttempt.objects.filter(paper=paper, student=student).first()
    if attempt and attempt.is_locked():
        messages.info(request, "This exam attempt is already submitted.")
        return redirect("student_exam_result", pk=attempt.pk)
    if request.method == "POST":
        start_or_get_attempt(student=student, paper=paper, request=request)
        return redirect("student_take_exam", pk=paper.pk)
    return render(request, "portals/student/exams/start_exam.html", {"student": student, "paper": paper, "attempt": attempt, "question_count": paper.questions.count()})


@role_required(Role.STUDENT)
def take_exam(request, pk: int):
    student = _get_student_profile(request)
    paper = get_object_or_404(ExamPaper.objects.select_related("exam", "offering__course").prefetch_related("questions__question"), pk=pk, is_published=True)
    if not student_is_allowed_for_paper(student, paper):
        messages.error(request, "You are not enrolled in this course.")
        return redirect("student_exams_dashboard")
    if not paper_is_online_available(paper):
        messages.error(request, "This exam is not available online.")
        return redirect("student_exams_dashboard")
    attempt = OnlineExamAttempt.objects.filter(paper=paper, student=student).first()
    if not attempt:
        messages.info(request, "Please start the exam first.")
        return redirect("student_exam_start", pk=paper.pk)
    if attempt.status in [OnlineExamAttempt.SUBMITTED, OnlineExamAttempt.AUTO_SUBMITTED, OnlineExamAttempt.GRADED]:
        messages.info(request, "You have already submitted this exam.")
        return redirect("student_exam_result", pk=attempt.pk)
    questions = ordered_questions_for_attempt(attempt)
    if request.method == "POST":
        save_attempt_responses(attempt, request, questions=questions)
        expired = attempt.is_expired()
        if request.POST.get("action") == "submit" or expired:
            submit_attempt(attempt, request=request, auto=expired)
            messages.success(request, "Exam submitted successfully." if not expired else "Time expired. Your exam has been submitted.")
            return redirect("student_exam_result", pk=attempt.pk)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "time_remaining": attempt.time_remaining()})
        messages.success(request, "Your answers have been saved.")
    if attempt.is_expired():
        submit_attempt(attempt, request=request, auto=True)
        messages.warning(request, "Time expired. Your exam has been submitted.")
        return redirect("student_exam_result", pk=attempt.pk)
    return render(request, "portals/student/exams/take_exam.html", {"student": student, "paper": paper, "attempt": attempt, "question_rows": responses_with_questions(attempt), "time_remaining": attempt.time_remaining()})


@role_required(Role.STUDENT)
def exam_security_event(request, pk: int):
    attempt = get_object_or_404(OnlineExamAttempt, pk=pk, student=_get_student_profile(request))
    if request.method == "POST" and not attempt.is_locked():
        attempt.browser_focus_warnings += 1
        attempt.save(update_fields=["browser_focus_warnings"])
    return JsonResponse({"ok": True, "warnings": attempt.browser_focus_warnings})


@role_required(Role.STUDENT)
def exam_result(request, pk: int):
    student = _get_student_profile(request)
    attempt = get_object_or_404(OnlineExamAttempt.objects.select_related("paper__exam", "paper__offering__course"), pk=pk, student=student)
    if not results_visible_for_paper(attempt.paper) and attempt.status != OnlineExamAttempt.GRADED:
        messages.info(request, "Results will be available after grading and publishing.")
        return redirect("student_exams_dashboard")
    score = ExamScore.objects.filter(paper=attempt.paper, student=student).first()
    return render(request, "portals/student/exams/exam_result.html", {"student": student, "attempt": attempt, "rows": responses_with_questions(attempt), "score": score})


@role_required(Role.STUDENT)
def exam_report_card_pdf(request, exam_id: int):
    student = _get_student_profile(request)
    exam = get_object_or_404(Exam, pk=exam_id)
    scores = list(ExamScore.objects.filter(student=student, paper__exam=exam, paper__results_published=True, paper__report_cards_enabled=True).select_related("paper", "paper__offering__course", "paper__exam"))
    if not scores:
        messages.error(request, "No published report card results are available for this exam.")
        return redirect("student_exam_results")
    org = get_or_create_organization()
    buf = generate_exam_report_card_pdf(student=student, exam=exam, scores=scores, org=org)
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="exam_report_card_{exam.id}_{student.student_id}.pdf"'
    return response
