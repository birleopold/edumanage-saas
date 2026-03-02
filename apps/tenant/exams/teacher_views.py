from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.academics.models import Enrollment
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import (
    SESSION_CURRENT_CAMPUS_ID,
    get_current_campus,
    get_or_create_organization,
    set_current_campus,
)
from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .models import ExamPaper, ExamScore


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _apply_campus_selection_from_request(request):
    if "campus" not in request.GET:
        return

    raw = request.GET.get("campus")
    if raw == "":
        request.session.pop(SESSION_CURRENT_CAMPUS_ID, None)
        return

    try:
        campus_id = int(raw)
    except (TypeError, ValueError):
        return

    org = get_or_create_organization()
    campus = Campus.objects.filter(organization=org, id=campus_id, is_active=True).first()
    if campus:
        set_current_campus(request, campus)


@role_required(Role.TEACHER)
def home(request):
    _apply_campus_selection_from_request(request)

    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset()
    current_campus = get_current_campus(request)
    selected_campus_id = current_campus.id if current_campus else None

    qs = ExamPaper.objects.select_related(
        "exam",
        "exam__term",
        "exam__term__year",
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
    ).filter(offering__teacher=teacher)

    if selected_campus_id:
        qs = qs.filter(offering__campus_id=selected_campus_id)

    if q:
        qs = qs.filter(Q(exam__name__icontains=q) | Q(offering__course__name__icontains=q) | Q(offering__course__code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/teacher/exams/home.html",
        {
            "teacher": teacher,
            "papers": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": selected_campus_id,
        },
    )


@role_required(Role.TEACHER)
def paper_grade(request, pk: int):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

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

    if paper.offering.teacher_id != teacher.id:
        return HttpResponseForbidden("You are not allowed to grade this paper.")

    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    per_page = _parse_per_page(request, default=50)
    page_number = request.GET.get("page") or 1

    enrollments_qs = Enrollment.objects.select_related("student").filter(
        offering=paper.offering,
        status=Enrollment.ACTIVE,
    )
    if q:
        enrollments_qs = enrollments_qs.filter(
            Q(student__student_id__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
        )

    paginator = Paginator(enrollments_qs, per_page)
    page_obj = paginator.get_page(page_number)

    existing = {
        s.student_id: s
        for s in ExamScore.objects.filter(paper=paper, student_id__in=[e.student_id for e in page_obj.object_list])
    }

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle_publish":
            paper.is_published = not paper.is_published
            paper.save(update_fields=["is_published"])
            messages.success(request, "Publish status updated.")
            return redirect("teacher_exam_paper_grade", pk=paper.pk)

        student_ids = request.POST.getlist("student_ids")
        updated = 0
        with transaction.atomic():
            for sid in student_ids:
                score_raw = request.POST.get(f"score_{sid}")
                note = request.POST.get(f"note_{sid}") or ""

                if score_raw is None or score_raw == "":
                    value = None
                else:
                    try:
                        value = float(score_raw)
                    except ValueError:
                        value = None

                ExamScore.objects.update_or_create(
                    paper=paper,
                    student_id=sid,
                    defaults={"score": value, "note": note, "graded_by": teacher},
                )
                updated += 1

        messages.success(request, f"Saved scores for {updated} student(s).")
        return redirect("teacher_exam_paper_grade", pk=paper.pk)

    return render(
        request,
        "portals/teacher/exams/grade.html",
        {
            "teacher": teacher,
            "paper": paper,
            "enrollments": page_obj.object_list,
            "page_obj": page_obj,
            "existing_scores": existing,
            "q": q,
            "per_page": per_page,
        },
    )
