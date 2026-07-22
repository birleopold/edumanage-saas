from decimal import Decimal

from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.campus_permissions import enforce_campus_scope, get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required, role_required, roles_required
from apps.tenant.portals.role_navigation import is_admin_portal_user
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role

from .forms import ChoiceForm, GradeAnswerForm, QuestionForm, QuizForm, QuizSubmitForm
from .models import Quiz, QuizAnswer, QuizAttempt, QuizQuestion


QUIZ_MANAGEMENT_ROLES = (Role.TEACHER, Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL)


def _teacher_profile(request):
    return getattr(request.user, "teacher_profile", None)


def _student_profile(request):
    return getattr(request.user, "student_profile", None)


def _teacher_quizzes(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return Quiz.objects.none()
    return Quiz.objects.select_related("course_offering", "campus").filter(
        course_offering__teacher=teacher
    )


def _management_quizzes(request):
    queryset = Quiz.objects.select_related("course_offering", "campus")
    if is_admin_portal_user(request.user):
        return enforce_campus_scope(queryset, request.user)
    if request.user.has_role(Role.TEACHER):
        return _teacher_quizzes(request)
    return queryset.none()


def _management_context(request, **context):
    return {"base_template": base_template_for(request.user), **context}


def _management_form_scope(request):
    if is_admin_portal_user(request.user):
        return None, get_user_campus_scope(request.user)
    teacher = _teacher_profile(request)
    return teacher, getattr(teacher, "campus", None)


def _available_quizzes_for_student(student):
    if student is None:
        return Quiz.objects.none()
    offering_ids = Enrollment.objects.filter(
        student=student,
        status=Enrollment.ACTIVE,
    ).values_list("offering_id", flat=True)
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
    attempt.save(
        update_fields=[
            "status",
            "completed_at",
            "score",
            "max_score",
            "percentage",
            "passed",
        ]
    )
    return attempt


@admin_portal_required
def admin_quiz_analytics(request):
    base = enforce_campus_scope(
        Quiz.objects.select_related("course_offering", "campus"),
        request.user,
    )
    quizzes = base.annotate(
        attempt_count=Count("attempts", distinct=True),
        avg_score=Avg("attempts__percentage"),
    ).order_by("-created_at")
    course_summary = (
        base.values("course_offering__course__name")
        .annotate(
            total=Count("id"),
            attempts=Count("attempts", distinct=True),
            average=Avg("attempts__percentage"),
        )
        .order_by("course_offering__course__name")
    )
    class_summary = (
        base.values("course_offering__class_group__name")
        .annotate(
            total=Count("id"),
            attempts=Count("attempts", distinct=True),
            average=Avg("attempts__percentage"),
        )
        .order_by("course_offering__class_group__name")
    )
    return render(
        request,
        "portals/admin/quizzes/analytics.html",
        {
            "quizzes": quizzes[:80],
            "course_summary": course_summary,
            "class_summary": class_summary,
        },
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def teacher_quiz_list(request):
    quizzes = _management_quizzes(request).order_by("-created_at")
    return render(
        request,
        "portals/teacher/quizzes/list.html",
        _management_context(request, quizzes=quizzes),
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def quiz_create(request):
    teacher, campus_scope = _management_form_scope(request)
    form = QuizForm(
        request.POST or None,
        teacher=teacher,
        campus_scope=campus_scope,
    )
    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.created_by = request.user
        quiz.save()
        form.save_m2m()
        form.assign_class_group_students(quiz)
        messages.success(request, "Quiz created. Add questions before publishing.")
        return redirect("teacher_quiz_detail", pk=quiz.pk)
    return render(
        request,
        "portals/teacher/quizzes/form.html",
        _management_context(request, form=form, mode="create"),
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def quiz_detail(request, pk):
    quiz = get_object_or_404(
        _management_quizzes(request).prefetch_related("questions__choices", "students"),
        pk=pk,
    )
    attempts = quiz.attempts.select_related("student").order_by("-started_at")
    return render(
        request,
        "portals/teacher/quizzes/detail.html",
        _management_context(request, quiz=quiz, attempts=attempts),
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def quiz_edit(request, pk):
    quiz = get_object_or_404(_management_quizzes(request), pk=pk)
    teacher, campus_scope = _management_form_scope(request)
    form = QuizForm(
        request.POST or None,
        instance=quiz,
        teacher=teacher,
        campus_scope=campus_scope,
    )
    if request.method == "POST" and form.is_valid():
        quiz = form.save()
        form.assign_class_group_students(quiz)
        messages.success(request, "Quiz updated.")
        return redirect("teacher_quiz_detail", pk=quiz.pk)
    return render(
        request,
        "portals/teacher/quizzes/form.html",
        _management_context(request, form=form, quiz=quiz, mode="edit"),
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
@require_POST
def quiz_toggle_publish(request, pk):
    quiz = get_object_or_404(_management_quizzes(request), pk=pk)
    quiz.is_active = not quiz.is_active
    quiz.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "Quiz publication status updated.")
    return redirect("teacher_quiz_detail", pk=quiz.pk)


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def question_create(request, quiz_pk):
    quiz = get_object_or_404(_management_quizzes(request), pk=quiz_pk)
    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.quiz = quiz
        question.save()
        messages.success(request, "Question added.")
        return redirect("teacher_quiz_detail", pk=quiz.pk)
    return render(
        request,
        "portals/teacher/quizzes/question_form.html",
        _management_context(request, form=form, quiz=quiz),
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def choice_create(request, question_pk):
    question = get_object_or_404(
        QuizQuestion.objects.select_related("quiz").filter(
            quiz_id__in=_management_quizzes(request).values("pk")
        ),
        pk=question_pk,
    )
    form = ChoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        choice = form.save(commit=False)
        choice.question = question
        choice.save()
        messages.success(request, "Choice added.")
        return redirect("teacher_quiz_detail", pk=question.quiz.pk)
    return render(
        request,
        "portals/teacher/quizzes/option_form.html",
        _management_context(request, form=form, question=question),
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def attempt_detail(request, pk):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "student")
        .prefetch_related("answers__question", "answers__selected_choice")
        .filter(quiz_id__in=_management_quizzes(request).values("pk")),
        pk=pk,
    )
    return render(
        request,
        "portals/teacher/quizzes/attempt_detail.html",
        _management_context(request, attempt=attempt),
    )


@roles_required(*QUIZ_MANAGEMENT_ROLES)
def grade_answer(request, pk):
    answer = get_object_or_404(
        QuizAnswer.objects.select_related("attempt", "attempt__quiz", "question").filter(
            attempt__quiz_id__in=_management_quizzes(request).values("pk")
        ),
        pk=pk,
    )
    form = GradeAnswerForm(request.POST or None, instance=answer)
    if request.method == "POST" and form.is_valid():
        form.save()
        answer.attempt.calculate_score()
        answer.attempt.status = QuizAttempt.GRADED
        answer.attempt.graded_by = request.user
        answer.attempt.graded_at = timezone.now()
        answer.attempt.save(
            update_fields=[
                "status",
                "score",
                "max_score",
                "percentage",
                "passed",
                "graded_by",
                "graded_at",
            ]
        )
        messages.success(request, "Answer graded and attempt score refreshed.")
        return redirect("teacher_quiz_attempt_detail", pk=answer.attempt.pk)
    return render(
        request,
        "portals/teacher/quizzes/grade_answer.html",
        _management_context(request, form=form, answer=answer),
    )


@role_required(Role.STUDENT)
def student_quiz_list(request):
    student = _student_profile(request)
    quizzes = _available_quizzes_for_student(student)
    attempts = (
        QuizAttempt.objects.filter(student=student).select_related("quiz")
        if student
        else QuizAttempt.objects.none()
    )
    return render(
        request,
        "portals/student/quizzes/list.html",
        {"quizzes": quizzes, "attempts": attempts},
    )


@role_required(Role.STUDENT)
def student_take_quiz(request, pk):
    student = _student_profile(request)
    quiz = get_object_or_404(
        _available_quizzes_for_student(student).prefetch_related("questions__choices"),
        pk=pk,
    )
    attempt, _ = QuizAttempt.objects.get_or_create(
        quiz=quiz,
        student=student,
        defaults={"max_score": _quiz_total_points(quiz)},
    )
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

    return render(
        request,
        "portals/student/quizzes/take.html",
        {"quiz": quiz, "attempt": attempt, "form": form},
    )


@role_required(Role.STUDENT)
def student_quiz_result(request, pk):
    student = _student_profile(request)
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "student").prefetch_related(
            "answers__question",
            "answers__selected_choice",
        ),
        pk=pk,
        student=student,
    )
    return render(request, "portals/student/quizzes/result.html", {"attempt": attempt})
