from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .models import ExamPaper, OnlineExamAttempt, StudentResponse
from .services import finalize_manual_marking, mark_response, publish_results, responses_with_questions


def _teacher(request):
    return TeacherProfile.objects.filter(user=request.user).first()


def _paper_for_teacher(teacher, pk):
    paper = get_object_or_404(ExamPaper.objects.select_related("exam", "offering", "offering__course"), pk=pk)
    if paper.offering.teacher_id != teacher.id:
        return None
    return paper


@role_required(Role.TEACHER)
def paper_online_attempts(request, pk: int):
    teacher = _teacher(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")
    paper = _paper_for_teacher(teacher, pk)
    if not paper:
        return HttpResponseForbidden("This paper is not assigned to this teacher.")
    if request.method == "POST" and request.POST.get("action") == "toggle_results":
        publish_results(paper, not paper.results_published)
        messages.success(request, "Result visibility updated.")
        return redirect("teacher_exam_online_attempts", pk=paper.pk)
    qs = OnlineExamAttempt.objects.filter(paper=paper).select_related("student", "paper", "paper__exam")
    status = request.GET.get("status") or ""
    if status:
        qs = qs.filter(status=status)
    page_obj = Paginator(qs.order_by("-started_at"), 50).get_page(request.GET.get("page") or 1)
    return render(request, "portals/teacher/exams/online_attempts.html", {"teacher": teacher, "paper": paper, "attempts": page_obj.object_list, "page_obj": page_obj, "status": status})


@role_required(Role.TEACHER)
def online_attempt_mark(request, pk: int):
    teacher = _teacher(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")
    attempt = get_object_or_404(OnlineExamAttempt.objects.select_related("paper", "paper__offering", "paper__offering__course", "student"), pk=pk)
    if attempt.paper.offering.teacher_id != teacher.id:
        return HttpResponseForbidden("This paper is not assigned to this teacher.")
    if request.method == "POST":
        updated = 0
        for response in StudentResponse.objects.filter(attempt=attempt).select_related("exam_question__question"):
            score_raw = request.POST.get(f"marks_{response.id}")
            feedback = request.POST.get(f"feedback_{response.id}") or ""
            if score_raw not in (None, ""):
                try:
                    mark_response(response, score_raw=score_raw, feedback=feedback, teacher=teacher)
                    updated += 1
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect("teacher_exam_attempt_mark", pk=attempt.pk)
        finalize_manual_marking(attempt, graded_by=teacher)
        messages.success(request, f"Saved marking for {updated} response(s).")
        return redirect("teacher_exam_attempt_mark", pk=attempt.pk)
    return render(request, "portals/teacher/exams/attempt_mark.html", {"teacher": teacher, "attempt": attempt, "rows": responses_with_questions(attempt)})
