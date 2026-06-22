from decimal import Decimal

from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.permissions import admin_portal_required, role_required, roles_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .forms import ChoiceForm, GradeAnswerForm, QuestionForm, QuizForm, QuizSubmitForm
from .models import Quiz, QuizAnswer, QuizAttempt, QuizQuestion


def _teacher_profile(request):
    return getattr(request.user, "teacher_profile", None)


def _student_profile(request):
    return getattr(request.user, "student_profile", None)


def _teacher_quizzes(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return Quiz.objects.none()
    return Quiz.objects.select_related("course_offering", "campus").filter(course_offering__teacher=teacher)


def _available_quizzes_for_student(student):
    offering_ids = Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list("offering_id", flat=True)
    now = timezone.now()
    return (
        Quiz.objects.select_related("course_offering", "campus")
        .filter(is_active=True)
        .filter(Q(available_from__isnull=True) | Q(available_from__lte=now))
        .filter(Q(available_until__isnull=True) | Q(available_until__gte=now))
        .filter(Q(students=student) | Q(students__isnull=True, course_offering_id__in=offering_ids))
        .distinct()
    )


def _quiz_total_points(quiz):
    return sum((question.points or Decimal("0")) for question in quiz.questions.all())


def _score_attempt(attempt):
    for answer in attempt.answers.select_related("question", "selected_choice"):
        answer.auto_grade()
    attempt.calculate_score()
    attempt.status = QuizAttempt.COMPLETED
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["status", "completed_at", "score", "max_score", "percentage", "passed"])
    return attempt


@admin_portal_required
def admin_quiz_analytics(request):
    quizzes = Quiz.objects.select_related("course_offering", "campus").annotate(
        attempt_count=Count("attempts", distinct=True),
        avg_score=Avg("attempts__percentage"),
    ).order_by("-created_at")
    course_summary = (
        Quiz.objects.values("course_offering__course__name")
        .annotate(total=Count("id"), attempts=Count("attempts", distinct=True), average=Avg("attempts__percentage"))
        .order_by("course_offering__course__name")
    )
    class_summary = (
        Quiz.objects.values("course_offering__class_group__name")
        .annotate(total=Count("id"), attempts=Count("attempts", distinct=True), average=Avg("attempts__percentage"))
        .order_by("course_offering__class_group__name")
    )
    return render(
        request,
        "portals/admin/quizzes/analytics.html",
        {"quizzes": quizzes[:80], "course_summary": course_summary, "class_summary": class_summary},
    )


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def teacher_quiz_list(request):
    quizzes = _teacher_quizzes(request) if request.user.has_role(Role.TEACHER) else Quiz.objects.select_related("course_offering", "campus").all()
    return render(request, "portals/teacher/quizzes/list.html", {"quizzes": quizzes.order_by("-created_at")})


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def quiz_create(request):
    teacher = _teacher_profile(request) if request.user.has_role(Role.TEACHER) else None
    form = QuizForm(request.POST or None, teacher=teacher)
    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.created_by = request.user
        quiz.save()
        form.instance = quiz
        form.save_m2m()
        class_group = form.cleaned_data.get("assign_class_group")
        if class_group:
            students = StudentProfile.objects.filter(stream__class_group=class_group, is_active=True)
            quiz.students.add(*students)
        messages.success(request, "Quiz created. Add questions before publishing.")
        return redirect("teacher_quiz_detail", pk=quiz.pk)
    return render(request, "portals/teacher/quizzes/form.html", {"form": form, "mode": "create"})


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def quiz_detail(request, pk):
    base_qs = _teacher_quizzes(request) if request.user.has_role(Role.TEACHER) else Quiz.objects.all()
    quiz = get_object_or_404(base_qs.select_related("course_offering", "campus").prefetch_related("questions__choices", "students"), pk=pk)
    attempts = quiz.attempts.select_related("student").order_by("-started_at")
    return render(request, "portals/teacher/quizzes/detail.html", {"quiz": quiz, "attempts": attempts})


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def quiz_edit(request, pk):
    base_qs = _teacher_quizzes(request) if request.user.has_role(Role.TEACHER) else Quiz.objects.all()
    quiz = get_object_or_404(base_qs, pk=pk)
    teacher = _teacher_profile(request) if request.user.has_role(Role.TEACHER) else None
    form = QuizForm(request.POST or None, instance=quiz, teacher=teacher)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Quiz updated.")
        return redirect("teacher_quiz_detail", pk=quiz.pk)
    return render(request, "portals/teacher/quizzes/form.html", {"form": form, "quiz": quiz, "mode": "edit"})


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
@require_POST
def quiz_toggle_publish(request, pk):
    base_qs = _teacher_quizzes(request) if request.user.has_role(Role.TEACHER) else Quiz.objects.all()
    quiz = get_object_or_404(base_qs, pk=pk)
    quiz.is_active = not quiz.is_active
    quiz.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "Quiz publication status updated.")
    return redirect("teacher_quiz_detail", pk=quiz.pk)


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def question_create(request, quiz_pk):
    base_qs = _teacher_quizzes(request) if request.user.has_role(Role.TEACHER) else Quiz.objects.all()
    quiz = get_object_or_404(base_qs, pk=quiz_pk)
    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.quiz = quiz
        question.save()
        messages.success(request, "Question added.")
        return redirect("teacher_quiz_detail", pk=quiz.pk)
    return render(request, "portals/teacher/quizzes/question_form.html", {"form": form, "quiz": quiz})


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def choice_create(request, question_pk):
    question = get_object_or_404(QuizQuestion.objects.select_related("quiz"), pk=question_pk)
    if request.user.has_role(Role.TEACHER) and question.quiz.course_offering.teacher != _teacher_profile(request):
        return redirect("teacher_quiz_list")
    form = ChoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        choice = form.save(commit=False)
        choice.question = question
        choice.save()
        messages.success(request, "Choice added.")
        return redirect("teacher_quiz_detail", pk=question.quiz.pk)
    return render(request, "portals/teacher/quizzes/option_form.html", {"form": form, "question": question})


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def attempt_detail(request, pk):
    attempt = get_object_or_404(QuizAttempt.objects.select_related("quiz", "student").prefetch_related("answers__question", "answers__selected_choice"), pk=pk)
    if request.user.has_role(Role.TEACHER) and attempt.quiz.course_offering.teacher != _teacher_profile(request):
        return redirect("teacher_quiz_list")
    return render(request, "portals/teacher/quizzes/attempt_detail.html", {"attempt": attempt})


@roles_required(Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN)
def grade_answer(request, pk):
    answer = get_object_or_404(QuizAnswer.objects.select_related("attempt", "attempt__quiz", "question"), pk=pk)
    if request.user.has_role(Role.TEACHER) and answer.attempt.quiz.course_offering.teacher != _teacher_profile(request):
        return redirect("teacher_quiz_list")
    form = GradeAnswerForm(request.POST or None, instance=answer)
    if request.method == "POST" and form.is_valid():
        form.save()
        answer.attempt.calculate_score()
        answer.attempt.status = QuizAttempt.GRADED
        answer.attempt.graded_by = request.user
        answer.attempt.graded_at = timezone.now()
        answer.attempt.save(update_fields=["status", "score", "max_score", "percentage", "passed", "graded_by", "graded_at"])
        messages.success(request, "Answer graded and attempt score refreshed.")
        return redirect("teacher_quiz_attempt_detail", pk=answer.attempt.pk)
    return render(request, "portals/teacher/quizzes/grade_answer.html", {"form": form, "answer": answer})


@role_required(Role.STUDENT)
def student_quiz_list(request):
    student = _student_profile(request)
    quizzes = _available_quizzes_for_student(student) if student else Quiz.objects.none()
    attempts = QuizAttempt.objects.filter(student=student).select_related("quiz") if student else QuizAttempt.objects.none()
    return render(request, "portals/student/quizzes/list.html", {"quizzes": quizzes, "attempts": attempts})


@role_required(Role.STUDENT)
def student_take_quiz(request, pk):
    student = _student_profile(request)
    quiz = get_object_or_404(_available_quizzes_for_student(student).prefetch_related("questions__choices"), pk=pk)
    attempt, created = QuizAttempt.objects.get_or_create(quiz=quiz, student=student, defaults={"max_score": _quiz_total_points(quiz)})
    if attempt.status != QuizAttempt.IN_PROGRESS:
        return redirect("student_quiz_result", pk=attempt.pk)

    form = QuizSubmitForm(request.POST or None, quiz=quiz)
    if request.method == "POST" and form.is_valid():
        for field in form.fields.values():
            question = field.question
            value = form.cleaned_data.get(f"question_{question.id}")
            answer, _ = QuizAnswer.objects.get_or_create(attempt=attempt, question=question)
            if question.question_type == QuizQuestion.MULTIPLE_CHOICE:
                answer.selected_choice = value
                answer.answer_text = value.choice_text if value else ""
            else:
                answer.answer_text = value or ""
                answer.selected_choice = None
            answer.answered_at = timezone.now()
            answer.save()
        _score_attempt(attempt)
        messages.success(request, "Quiz submitted.")
        return redirect("student_quiz_result", pk=attempt.pk)

    return render(request, "portals/student/quizzes/take.html", {"quiz": quiz, "attempt": attempt, "form": form})


@role_required(Role.STUDENT)
def student_quiz_result(request, pk):
    student = _student_profile(request)
    attempt = get_object_or_404(QuizAttempt.objects.select_related("quiz", "student").prefetch_related("answers__question", "answers__selected_choice"), pk=pk, student=student)
    return render(request, "portals/student/quizzes/result.html", {"attempt": attempt})
