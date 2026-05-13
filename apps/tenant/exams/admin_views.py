from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from django.contrib import messages
from django.db.models import Avg, Count, Max, Min
from django.http import HttpResponse
from django.utils import timezone

from .forms import (
    ExamForm,
    ExamPaperForm,
    ExamQuestionForm,
    ExamScheduleForm,
    QuestionBankForm,
    SeatAllocationForm,
)
from .models import (
    Exam,
    ExamAnalytics,
    ExamPaper,
    ExamQuestion,
    ExamSchedule,
    ExamScore,
    OnlineExamAttempt,
    QuestionBank,
    SeatAllocation,
)
from .utils import (
    allocate_seats_auto,
    assign_grades,
    calculate_exam_analytics,
    calculate_student_rank,
    generate_admit_card_pdf,
)


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _selected_campus_id(request):
    current = get_current_campus(request)
    if "campus" in request.GET:
        raw = request.GET.get("campus")
        if raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return current.id if current else None


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@admin_portal_required
def exam_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Exam.objects.select_related("term", "term__year").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(term__name__icontains=q) | Q(term__year__name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/exams/exams_list.html",
        {"exams": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def exam_create(request):
    if request.method == "POST":
        form = ExamForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam created successfully.")
            return redirect("admin_exams_list")
    else:
        form = ExamForm()

    return render(request, "portals/admin/exams/exam_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def exam_edit(request, pk: int):
    obj = get_object_or_404(Exam, pk=pk)

    if request.method == "POST":
        form = ExamForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam updated successfully.")
            return redirect("admin_exams_list")
    else:
        form = ExamForm(instance=obj)

    return render(
        request,
        "portals/admin/exams/exam_form.html",
        {"form": form, "mode": "edit", "exam": obj},
    )


@admin_portal_required
def paper_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)

    qs = ExamPaper.objects.select_related(
        "exam",
        "exam__term",
        "exam__term__year",
        "offering",
        "offering__campus",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "offering__teacher",
    ).all()

    if campus_id:
        qs = qs.filter(offering__campus_id=campus_id)

    if q:
        qs = qs.filter(
            Q(exam__name__icontains=q)
            | Q(offering__course__name__icontains=q)
            | Q(offering__course__code__icontains=q)
            | Q(offering__class_group__name__icontains=q)
            | Q(offering__teacher__first_name__icontains=q)
            | Q(offering__teacher__last_name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/exams/papers_list.html",
        {
            "papers": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def paper_create(request):
    if request.method == "POST":
        form = ExamPaperForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam paper created successfully.")
            return redirect("admin_exam_papers_list")
    else:
        form = ExamPaperForm()

    return render(request, "portals/admin/exams/paper_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def paper_edit(request, pk: int):
    obj = get_object_or_404(ExamPaper, pk=pk)

    if request.method == "POST":
        form = ExamPaperForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam paper updated successfully.")
            return redirect("admin_exam_papers_list")
    else:
        form = ExamPaperForm(instance=obj)

    return render(
        request,
        "portals/admin/exams/paper_form.html",
        {"form": form, "mode": "edit", "paper": obj},
    )


@admin_portal_required
def paper_detail(request, pk: int):
    paper = get_object_or_404(
        ExamPaper.objects.select_related('exam', 'offering__course').prefetch_related('questions__question', 'schedules'),
        pk=pk
    )
    
    questions = paper.questions.all().order_by('order')
    schedules = paper.schedules.all()
    
    # Get analytics
    try:
        analytics = paper.analytics
    except ExamAnalytics.DoesNotExist:
        analytics = None
    
    return render(
        request,
        "portals/admin/exams/paper_detail.html",
        {"paper": paper, "questions": questions, "schedules": schedules, "analytics": analytics},
    )


@admin_portal_required
def paper_scores(request, pk: int):
    paper = get_object_or_404(
        ExamPaper.objects.select_related(
            "exam",
            "exam__term",
            "exam__term__year",
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
            "offering__class_group",
        ),
        pk=pk,
    )

    scores = ExamScore.objects.filter(paper=paper).select_related("student").order_by('-score')

    return render(
        request,
        "portals/admin/exams/paper_scores.html",
        {"paper": paper, "scores": scores},
    )


@admin_portal_required
def question_bank_list(request):
    q = (request.GET.get("q") or "").strip()
    course_filter = request.GET.get("course", "")
    type_filter = request.GET.get("type", "")
    difficulty_filter = request.GET.get("difficulty", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = QuestionBank.objects.select_related("course", "created_by").all()
    
    if q:
        qs = qs.filter(Q(question_text__icontains=q) | Q(tags__icontains=q) | Q(course__name__icontains=q))
    if course_filter:
        qs = qs.filter(course_id=course_filter)
    if type_filter:
        qs = qs.filter(question_type=type_filter)
    if difficulty_filter:
        qs = qs.filter(difficulty=difficulty_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/exams/question_bank_list.html",
        {
            "questions": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "course_filter": course_filter,
            "type_filter": type_filter,
            "difficulty_filter": difficulty_filter,
            "per_page": per_page,
        },
    )


@admin_portal_required
def question_bank_create(request):
    if request.method == "POST":
        form = QuestionBankForm(request.POST, request.FILES)
        if form.is_valid():
            question = form.save(commit=False)
            if hasattr(request.user, 'teacher_profile'):
                question.created_by = request.user.teacher_profile
            question.save()
            messages.success(request, "Question created successfully.")
            return redirect("admin_question_bank_list")
    else:
        form = QuestionBankForm()

    return render(request, "portals/admin/exams/question_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def question_bank_edit(request, pk: int):
    obj = get_object_or_404(QuestionBank, pk=pk)

    if request.method == "POST":
        form = QuestionBankForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Question updated successfully.")
            return redirect("admin_question_bank_list")
    else:
        form = QuestionBankForm(instance=obj)

    return render(
        request,
        "portals/admin/exams/question_form.html",
        {"form": form, "mode": "edit", "question": obj},
    )


@admin_portal_required
def paper_questions(request, pk: int):
    paper = get_object_or_404(ExamPaper.objects.select_related('exam', 'offering__course'), pk=pk)
    questions = ExamQuestion.objects.filter(paper=paper).select_related('question').order_by('order')
    
    # Available questions from the same course
    available_questions = QuestionBank.objects.filter(
        course=paper.offering.course,
        is_active=True
    ).exclude(id__in=questions.values_list('question_id', flat=True))

    return render(
        request,
        "portals/admin/exams/paper_questions.html",
        {"paper": paper, "questions": questions, "available_questions": available_questions},
    )


@admin_portal_required
def paper_add_question(request, pk: int):
    paper = get_object_or_404(ExamPaper, pk=pk)
    
    if request.method == "POST":
        form = ExamQuestionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Question added to exam paper.")
            return redirect("admin_paper_questions", pk=pk)
    else:
        form = ExamQuestionForm(initial={'paper': paper})
        form.fields['question'].queryset = QuestionBank.objects.filter(
            course=paper.offering.course,
            is_active=True
        ).exclude(
            id__in=ExamQuestion.objects.filter(paper=paper).values_list('question_id', flat=True)
        )

    return render(request, "portals/admin/exams/add_question_to_paper.html", {"form": form, "paper": paper})


@admin_portal_required
def schedule_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = ExamSchedule.objects.select_related("paper__exam", "paper__offering__course", "invigilator").all()
    
    if q:
        qs = qs.filter(
            Q(room_name__icontains=q)
            | Q(paper__exam__name__icontains=q)
            | Q(paper__offering__course__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/exams/schedule_list.html",
        {"schedules": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def schedule_create(request):
    if request.method == "POST":
        form = ExamScheduleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam schedule created successfully.")
            return redirect("admin_exam_schedules_list")
    else:
        form = ExamScheduleForm()

    return render(request, "portals/admin/exams/schedule_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def schedule_edit(request, pk: int):
    obj = get_object_or_404(ExamSchedule, pk=pk)

    if request.method == "POST":
        form = ExamScheduleForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam schedule updated successfully.")
            return redirect("admin_exam_schedules_list")
    else:
        form = ExamScheduleForm(instance=obj)

    return render(
        request,
        "portals/admin/exams/schedule_form.html",
        {"form": form, "mode": "edit", "schedule": obj},
    )


@admin_portal_required
def schedule_detail(request, pk: int):
    schedule = get_object_or_404(
        ExamSchedule.objects.select_related('paper__exam', 'paper__offering__course', 'invigilator'),
        pk=pk
    )
    
    allocations = SeatAllocation.objects.filter(schedule=schedule).select_related('student').order_by('seat_number')

    return render(
        request,
        "portals/admin/exams/schedule_detail.html",
        {"schedule": schedule, "allocations": allocations},
    )


@admin_portal_required
def allocate_seats(request, pk: int):
    schedule = get_object_or_404(ExamSchedule, pk=pk)
    
    if request.method == "POST":
        from apps.tenant.students.models import StudentProfile
        
        student_ids = request.POST.getlist('students')
        seat_prefix = request.POST.get('seat_prefix', '')
        
        students = StudentProfile.objects.filter(id__in=student_ids)
        
        try:
            allocations = allocate_seats_auto(schedule, students, seat_prefix)
            messages.success(request, f"{len(allocations)} seats allocated successfully.")
            return redirect("admin_schedule_detail", pk=pk)
        except ValueError as e:
            messages.error(request, str(e))
    
    from apps.tenant.students.models import StudentProfile
    enrolled_students = StudentProfile.objects.filter(
        enrollments__offering=schedule.paper.offering,
        enrollments__is_active=True
    ).exclude(
        id__in=SeatAllocation.objects.filter(schedule=schedule).values_list('student_id', flat=True)
    ).distinct()

    return render(
        request,
        "portals/admin/exams/allocate_seats.html",
        {"schedule": schedule, "students": enrolled_students},
    )


@admin_portal_required
def generate_admit_card(request, pk: int):
    allocation = get_object_or_404(SeatAllocation.objects.select_related('student', 'schedule__paper__exam', 'schedule__paper__offering__course'), pk=pk)
    
    pdf_buffer = generate_admit_card_pdf(allocation)
    
    if not allocation.admit_card_generated:
        allocation.admit_card_generated = True
        allocation.admit_card_generated_at = timezone.now()
        allocation.save()
    
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="admit_card_{allocation.student.student_id}.pdf"'
    return response


@admin_portal_required
def paper_analytics(request, pk: int):
    paper = get_object_or_404(ExamPaper.objects.select_related('exam', 'offering__course'), pk=pk)
    
    analytics = calculate_exam_analytics(paper)
    
    # Question-wise analysis
    question_analysis = []
    for exam_q in paper.questions.all():
        from .models import StudentResponse
        responses = StudentResponse.objects.filter(exam_question=exam_q, is_correct__isnull=False)
        total = responses.count()
        correct = responses.filter(is_correct=True).count()
        
        question_analysis.append({
            'question': exam_q,
            'total_responses': total,
            'correct_responses': correct,
            'accuracy': (correct / total * 100) if total > 0 else 0
        })
    
    # Score distribution
    scores = ExamScore.objects.filter(paper=paper, score__isnull=False).order_by('score')
    
    return render(
        request,
        "portals/admin/exams/paper_analytics.html",
        {
            "paper": paper,
            "analytics": analytics,
            "question_analysis": question_analysis,
            "scores": scores,
        },
    )


@admin_portal_required
def calculate_ranks(request, pk: int):
    paper = get_object_or_404(ExamPaper, pk=pk)
    calculate_student_rank(paper)
    messages.success(request, "Ranks calculated successfully.")
    return redirect("admin_paper_scores", pk=pk)


@admin_portal_required
def assign_paper_grades(request, pk: int):
    paper = get_object_or_404(ExamPaper, pk=pk)
    
    if request.method == "POST":
        grade_boundaries = {
            'A': float(request.POST.get('grade_a', 90)),
            'B': float(request.POST.get('grade_b', 80)),
            'C': float(request.POST.get('grade_c', 70)),
            'D': float(request.POST.get('grade_d', 60)),
            'E': float(request.POST.get('grade_e', 50)),
        }
        
        assign_grades(paper, grade_boundaries)
        messages.success(request, "Grades assigned successfully.")
        return redirect("admin_paper_scores", pk=pk)
    
    return render(
        request,
        "portals/admin/exams/assign_grades.html",
        {"paper": paper},
    )


@admin_portal_required
def online_attempts_list(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = request.GET.get("status", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = OnlineExamAttempt.objects.select_related("student", "paper__exam", "paper__offering__course").all()
    
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(paper__exam__name__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/exams/online_attempts_list.html",
        {"attempts": page_obj.object_list, "page_obj": page_obj, "q": q, "status_filter": status_filter, "per_page": per_page},
    )
