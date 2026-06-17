from __future__ import annotations

import random
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.tenant.academics.models import Enrollment

from .models import (
    Exam,
    ExamAntiCheatEvent,
    ExamPaper,
    ExamQuestion,
    ExamScore,
    OnlineExamAttempt,
    QuestionBank,
    StudentResponse,
)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:2000]


def student_is_allowed_for_paper(student, paper: ExamPaper) -> bool:
    return Enrollment.objects.filter(student=student, offering=paper.offering, status=Enrollment.ACTIVE).exists()


def paper_is_online_available(paper: ExamPaper) -> bool:
    return paper.is_published and paper.exam.exam_mode in [Exam.ONLINE, Exam.HYBRID]


def ordered_questions_for_attempt(attempt: OnlineExamAttempt):
    qs = list(attempt.paper.questions.select_related("question").order_by("order", "id"))
    if not attempt.question_order:
        ordered_ids = [q.id for q in qs]
        if attempt.paper.randomize_questions:
            random.shuffle(ordered_ids)
        attempt.question_order = ordered_ids
        attempt.save(update_fields=["question_order"])
    order_map = {qid: idx for idx, qid in enumerate(attempt.question_order or [])}
    return sorted(qs, key=lambda q: order_map.get(q.id, 999999))


def log_exam_event(attempt: OnlineExamAttempt, event_type: str, request=None, metadata=None):
    event = ExamAntiCheatEvent.objects.create(
        attempt=attempt,
        event_type=event_type,
        ip_address=client_ip(request) if request else None,
        user_agent=user_agent(request) if request else "",
        metadata=metadata or {},
    )
    if event_type in [ExamAntiCheatEvent.FOCUS_LOST, ExamAntiCheatEvent.TAB_HIDDEN, ExamAntiCheatEvent.COPY_PASTE, ExamAntiCheatEvent.FULLSCREEN_EXIT]:
        attempt.browser_focus_warnings += 1
        attempt.last_activity_at = timezone.now()
        attempt.save(update_fields=["browser_focus_warnings", "last_activity_at"])
    return event


@transaction.atomic
def start_or_get_attempt(*, student, paper: ExamPaper, request=None) -> OnlineExamAttempt:
    attempt, created = OnlineExamAttempt.objects.get_or_create(
        paper=paper,
        student=student,
        defaults={
            "ip_address": client_ip(request) if request else None,
            "user_agent": user_agent(request) if request else "",
            "last_activity_at": timezone.now(),
        },
    )
    if created:
        ordered_questions_for_attempt(attempt)
        log_exam_event(attempt, ExamAntiCheatEvent.START, request=request)
    else:
        changed = []
        if request and not attempt.user_agent:
            attempt.user_agent = user_agent(request)
            changed.append("user_agent")
        attempt.last_activity_at = timezone.now()
        changed.append("last_activity_at")
        if changed:
            attempt.save(update_fields=changed)
    return attempt


def response_value_from_post(request, exam_question: ExamQuestion):
    raw = request.POST.get(f"question_{exam_question.id}", "")
    question = exam_question.question
    if question.question_type in [QuestionBank.MCQ, QuestionBank.TRUE_FALSE]:
        return {"selected_option": (raw or "").strip().upper()[:1], "answer_text": ""}
    return {"selected_option": "", "answer_text": (raw or "").strip()}


def save_attempt_responses(attempt: OnlineExamAttempt, request, questions=None):
    if attempt.is_locked():
        return 0
    questions = questions or ordered_questions_for_attempt(attempt)
    saved = 0
    for exam_q in questions:
        value = response_value_from_post(request, exam_q)
        if not value["selected_option"] and not value["answer_text"]:
            continue
        StudentResponse.objects.update_or_create(
            attempt=attempt,
            exam_question=exam_q,
            defaults=value,
        )
        saved += 1
    attempt.last_activity_at = timezone.now()
    attempt.save(update_fields=["last_activity_at"])
    log_exam_event(attempt, ExamAntiCheatEvent.SAVE, request=request, metadata={"saved_responses": saved})
    return saved


def score_attempt(attempt: OnlineExamAttempt):
    responses = StudentResponse.objects.filter(attempt=attempt).select_related("exam_question__question")
    total = Decimal("0")
    manual_pending = False
    for response in responses:
        if response.exam_question.question.is_objective():
            response.auto_grade()
        else:
            if response.marks_awarded is None:
                manual_pending = True
        if response.marks_awarded is not None:
            total += response.marks_awarded
    attempt.score = total
    attempt.status = OnlineExamAttempt.SUBMITTED if manual_pending else OnlineExamAttempt.GRADED
    attempt.save(update_fields=["score", "status"])
    sync_exam_score_from_attempt(attempt)
    return total, manual_pending


@transaction.atomic
def submit_attempt(attempt: OnlineExamAttempt, request=None, *, auto=False):
    if attempt.status in [OnlineExamAttempt.SUBMITTED, OnlineExamAttempt.AUTO_SUBMITTED, OnlineExamAttempt.GRADED]:
        return attempt
    attempt.status = OnlineExamAttempt.AUTO_SUBMITTED if auto else OnlineExamAttempt.SUBMITTED
    attempt.submitted_at = timezone.now()
    attempt.submitted_by_ip = client_ip(request) if request else None
    attempt.locked_at = timezone.now()
    attempt.locked_reason = "Time expired" if auto else "Submitted by student"
    attempt.last_activity_at = timezone.now()
    attempt.save(update_fields=["status", "submitted_at", "submitted_by_ip", "locked_at", "locked_reason", "last_activity_at"])
    log_exam_event(attempt, ExamAntiCheatEvent.AUTO_SUBMIT if auto else ExamAntiCheatEvent.SUBMIT, request=request)
    score_attempt(attempt)
    return attempt


def sync_exam_score_from_attempt(attempt: OnlineExamAttempt, graded_by=None):
    if attempt.score is None:
        return None
    score, _created = ExamScore.objects.update_or_create(
        paper=attempt.paper,
        student=attempt.student,
        defaults={
            "score": attempt.score,
            "note": f"Online attempt: {attempt.get_status_display()}",
            "graded_by": graded_by,
        },
    )
    score.calculate_percentage()
    return score


def attempt_has_manual_pending(attempt: OnlineExamAttempt) -> bool:
    return StudentResponse.objects.filter(
        attempt=attempt,
        exam_question__question__question_type__in=[QuestionBank.SHORT_ANSWER, QuestionBank.ESSAY],
        marks_awarded__isnull=True,
    ).exists()


def finalize_manual_marking(attempt: OnlineExamAttempt, graded_by=None):
    total = Decimal("0")
    for response in StudentResponse.objects.filter(attempt=attempt):
        if response.marks_awarded is not None:
            total += response.marks_awarded
    attempt.score = total
    if not attempt_has_manual_pending(attempt):
        attempt.status = OnlineExamAttempt.GRADED
    attempt.save(update_fields=["score", "status"])
    return sync_exam_score_from_attempt(attempt, graded_by=graded_by)


def mark_response(response: StudentResponse, *, score_raw, feedback, teacher=None):
    try:
        value = Decimal(str(score_raw or "0"))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid score.")
    if value < 0:
        raise ValueError("Score cannot be negative.")
    if value > response.exam_question.marks:
        raise ValueError("Score cannot exceed the question marks.")
    response.marks_awarded = value
    response.manual_feedback = feedback or ""
    response.manually_marked_by = teacher
    response.manually_marked_at = timezone.now()
    response.is_correct = value >= response.exam_question.marks
    response.save(update_fields=["marks_awarded", "manual_feedback", "manually_marked_by", "manually_marked_at", "is_correct"])
    return response


def results_visible_for_paper(paper: ExamPaper) -> bool:
    return bool(paper.results_published or paper.show_results_immediately)


def publish_results(paper: ExamPaper, publish=True):
    paper.results_published = bool(publish)
    paper.results_published_at = timezone.now() if publish else None
    paper.save(update_fields=["results_published", "results_published_at"])
    return paper


def responses_with_questions(attempt: OnlineExamAttempt):
    responses = StudentResponse.objects.filter(attempt=attempt).select_related("exam_question__question")
    response_map = {r.exam_question_id: r for r in responses}
    return [(exam_q, response_map.get(exam_q.id)) for exam_q in ordered_questions_for_attempt(attempt)]
