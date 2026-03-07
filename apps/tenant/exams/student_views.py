from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import (
    Exam,
    ExamPaper,
    ExamQuestion,
    ExamScore,
    OnlineExamAttempt,
    SeatAllocation,
    StudentResponse,
)
from .utils import auto_grade_attempt


def _get_student_profile(request):
    student = StudentProfile.objects.filter(user=request.user).first()
    if not student:
        raise HttpResponseForbidden("No student profile linked to this account.")
    return student


@role_required(Role.STUDENT)
def results(request):
    student = _get_student_profile(request)

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


@role_required(Role.STUDENT)
def my_exams(request):
    student = _get_student_profile(request)

    offering_ids = list(
        Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list("offering_id", flat=True)
    )

    papers = (
        ExamPaper.objects.select_related("exam", "offering__course")
        .filter(offering_id__in=offering_ids, is_published=True)
        .order_by("-exam__start_date", "offering__course__name")
    )

    return render(
        request,
        "portals/student/exams/my_exams.html",
        {"student": student, "papers": papers},
    )


@role_required(Role.STUDENT)
def my_schedules(request):
    student = _get_student_profile(request)

    allocations = SeatAllocation.objects.filter(student=student).select_related(
        "schedule__paper__exam",
        "schedule__paper__offering__course",
        "schedule__invigilator"
    ).order_by("schedule__date", "schedule__start_time")

    return render(
        request,
        "portals/student/exams/my_schedules.html",
        {"student": student, "allocations": allocations},
    )


@role_required(Role.STUDENT)
def take_exam(request, pk: int):
    student = _get_student_profile(request)
    paper = get_object_or_404(
        ExamPaper.objects.select_related("exam", "offering__course").prefetch_related("questions__question"),
        pk=pk,
        is_published=True
    )
    
    # Check if student is enrolled
    enrollment = Enrollment.objects.filter(student=student, offering=paper.offering, status=Enrollment.ACTIVE).first()
    if not enrollment:
        messages.error(request, "You are not enrolled in this course.")
        return redirect("student_exams_results")
    
    # Check if exam is online
    if paper.exam.exam_mode not in [Exam.ONLINE, Exam.HYBRID]:
        messages.error(request, "This exam is not available online.")
        return redirect("student_exams_results")
    
    # Get or create attempt
    attempt, created = OnlineExamAttempt.objects.get_or_create(
        paper=paper,
        student=student,
        defaults={'ip_address': request.META.get('REMOTE_ADDR')}
    )
    
    # Check if already submitted
    if attempt.status in [OnlineExamAttempt.SUBMITTED, OnlineExamAttempt.AUTO_SUBMITTED, OnlineExamAttempt.GRADED]:
        messages.info(request, "You have already submitted this exam.")
        return redirect("student_exam_result", pk=attempt.pk)
    
    # Check if time expired
    if attempt.is_expired():
        attempt.status = OnlineExamAttempt.AUTO_SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save()
        
        # Auto-grade
        auto_grade_attempt(attempt)
        
        messages.warning(request, "Exam time expired. Your exam has been auto-submitted.")
        return redirect("student_exam_result", pk=attempt.pk)
    
    # Get questions
    questions = paper.questions.all().order_by('order')
    if paper.randomize_questions and created:
        questions = questions.order_by('?')
    
    # Get existing responses
    responses = StudentResponse.objects.filter(attempt=attempt).select_related('exam_question__question')
    response_map = {r.exam_question_id: r for r in responses}
    
    # Handle form submission
    if request.method == "POST":
        # Save responses
        for exam_q in questions:
            question = exam_q.question
            
            if question.question_type in [question.MCQ, question.TRUE_FALSE]:
                selected = request.POST.get(f"question_{exam_q.id}")
                if selected:
                    StudentResponse.objects.update_or_create(
                        attempt=attempt,
                        exam_question=exam_q,
                        defaults={'selected_option': selected}
                    )
            else:
                answer = request.POST.get(f"question_{exam_q.id}", "").strip()
                if answer:
                    StudentResponse.objects.update_or_create(
                        attempt=attempt,
                        exam_question=exam_q,
                        defaults={'answer_text': answer}
                    )
        
        # Check if submitting
        if request.POST.get('action') == 'submit':
            attempt.status = OnlineExamAttempt.SUBMITTED
            attempt.submitted_at = timezone.now()
            attempt.save()
            
            # Auto-grade objective questions
            auto_grade_attempt(attempt)
            
            messages.success(request, "Exam submitted successfully!")
            return redirect("student_exam_result", pk=attempt.pk)
        
        messages.success(request, "Your answers have been saved.")
    
    return render(
        request,
        "portals/student/exams/take_exam.html",
        {
            "student": student,
            "paper": paper,
            "attempt": attempt,
            "questions": questions,
            "response_map": response_map,
            "time_remaining": attempt.time_remaining(),
        },
    )


@role_required(Role.STUDENT)
def exam_result(request, pk: int):
    student = _get_student_profile(request)
    attempt = get_object_or_404(
        OnlineExamAttempt.objects.select_related("paper__exam", "paper__offering__course"),
        pk=pk,
        student=student
    )
    
    # Check if results are available
    if not attempt.paper.show_results_immediately and attempt.status != OnlineExamAttempt.GRADED:
        messages.info(request, "Results will be available after grading is complete.")
        return redirect("student_exams_results")
    
    # Get responses
    responses = StudentResponse.objects.filter(attempt=attempt).select_related(
        'exam_question__question'
    ).order_by('exam_question__order')
    
    return render(
        request,
        "portals/student/exams/exam_result.html",
        {"student": student, "attempt": attempt, "responses": responses},
    )
