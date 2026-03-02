from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import ExamForm, ExamPaperForm
from .models import Exam, ExamPaper, ExamScore


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


@role_required(Role.ADMIN)
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


@role_required(Role.ADMIN)
def exam_create(request):
    if request.method == "POST":
        form = ExamForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_exams_list")
    else:
        form = ExamForm()

    return render(request, "portals/admin/exams/exam_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def exam_edit(request, pk: int):
    obj = get_object_or_404(Exam, pk=pk)

    if request.method == "POST":
        form = ExamForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_exams_list")
    else:
        form = ExamForm(instance=obj)

    return render(
        request,
        "portals/admin/exams/exam_form.html",
        {"form": form, "mode": "edit", "exam": obj},
    )


@role_required(Role.ADMIN)
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


@role_required(Role.ADMIN)
def paper_create(request):
    if request.method == "POST":
        form = ExamPaperForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_exam_papers_list")
    else:
        form = ExamPaperForm()

    return render(request, "portals/admin/exams/paper_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def paper_edit(request, pk: int):
    obj = get_object_or_404(ExamPaper, pk=pk)

    if request.method == "POST":
        form = ExamPaperForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_exam_papers_list")
    else:
        form = ExamPaperForm(instance=obj)

    return render(
        request,
        "portals/admin/exams/paper_form.html",
        {"form": form, "mode": "edit", "paper": obj},
    )


@role_required(Role.ADMIN)
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

    scores = ExamScore.objects.filter(paper=paper).select_related("student")

    return render(
        request,
        "portals/admin/exams/paper_scores.html",
        {"paper": paper, "scores": scores},
    )
