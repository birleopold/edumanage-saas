from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from urllib.parse import urlencode

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required

from .forms import (
    AcademicTermForm,
    AcademicYearForm,
    ClassGroupForm,
    CourseForm,
    CourseOfferingForm,
    EnrollmentForm,
    GradeRangeForm,
    GradingScaleForm,
    LevelForm,
    ProgramForm,
    StreamForm,
)
from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    GradeRange,
    GradingScale,
    Level,
    Program,
    Stream,
)

from apps.tenant.students.models import StudentProfile


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _selected_campus_id(request):
    current = get_current_campus(request)

    campus_filter = None
    if "campus" in request.GET:
        campus_filter = request.GET.get("campus")
    elif "campus" in request.POST:
        campus_filter = request.POST.get("campus")

    if campus_filter is None:
        return current.id if current else None

    if campus_filter == "":
        return None

    try:
        return int(campus_filter)
    except (TypeError, ValueError):
        return None


def _parse_per_page(request, raw=None, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = raw if raw is not None else request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _paginate_queryset(request, queryset, default_per_page: int = 25):
    per_page = _parse_per_page(request, default=default_per_page)
    page_number = request.GET.get("page") or 1
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page_number)
    return page_obj, per_page


def _simple_form(request, template, title, form, list_url_name):
    return render(
        request,
        template,
        {
            "title": title,
            "form": form,
            "list_url_name": list_url_name,
        },
    )


@admin_portal_required
def year_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = AcademicYear.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/years_list.html",
        {
            "years": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def academic_context(request):
    if request.method == "POST":
        action = request.POST.get("action")
        pk = request.POST.get("pk")

        if action == "set_current_year" and pk:
            year = get_object_or_404(AcademicYear, pk=pk)
            with transaction.atomic():
                AcademicYear.objects.update(is_current=False)
                year.is_current = True
                year.save(update_fields=["is_current"])
            messages.success(request, f"Current academic year set to: {year.name}.")
            return redirect("admin_academic_context")

        if action == "clear_current_year":
            AcademicYear.objects.update(is_current=False)
            messages.success(request, "Cleared current academic year.")
            return redirect("admin_academic_context")

        if action == "set_current_term" and pk:
            term = get_object_or_404(AcademicTerm, pk=pk)
            with transaction.atomic():
                AcademicTerm.objects.update(is_current=False)
                term.is_current = True
                term.save(update_fields=["is_current"])

                AcademicYear.objects.update(is_current=False)
                AcademicYear.objects.filter(pk=term.year_id).update(is_current=True)

            messages.success(request, f"Current academic term set to: {term}.")
            return redirect("admin_academic_context")

        if action == "clear_current_term":
            AcademicTerm.objects.update(is_current=False)
            messages.success(request, "Cleared current academic term.")
            return redirect("admin_academic_context")

        messages.error(request, "Invalid action.")
        return redirect("admin_academic_context")

    years = AcademicYear.objects.all().order_by("-name")
    terms = AcademicTerm.objects.select_related("year").all().order_by("-year__name", "order")
    current_year = AcademicYear.objects.filter(is_current=True).order_by("-name").first()
    current_term = AcademicTerm.objects.filter(is_current=True).select_related("year").first()

    return render(
        request,
        "portals/admin/academics/context.html",
        {
            "years": years,
            "terms": terms,
            "current_year": current_year,
            "current_term": current_term,
        },
    )


@admin_portal_required
def enrollment_bulk_status(request):
    offering_id = request.GET.get("offering") or request.POST.get("offering")
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page") or request.POST.get("per_page")

    offerings = CourseOffering.objects.select_related(
        "course",
        "term",
        "term__year",
        "class_group",
        "teacher",
    ).all()

    selected_offering = None
    if offering_id:
        selected_offering = offerings.filter(id=offering_id).first()

    enrollments_qs = Enrollment.objects.select_related(
        "student",
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
    ).all()

    if selected_offering:
        enrollments_qs = enrollments_qs.filter(offering=selected_offering)
    else:
        enrollments_qs = enrollments_qs.none()

    if q:
        enrollments_qs = enrollments_qs.filter(
            Q(student__student_id__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
        )

    per_page = _parse_per_page(request, raw=per_page_raw)
    page_number = request.GET.get("page") or 1
    paginator = Paginator(enrollments_qs, per_page)
    page_obj = paginator.get_page(page_number)

    if request.method == "POST":
        if not selected_offering:
            messages.error(request, "Please select an offering.")
            return redirect(reverse("admin_enrollment_bulk_status"))

        action = request.POST.get("action")
        enrollment_ids = request.POST.getlist("enrollment_ids")
        qs = Enrollment.objects.filter(offering=selected_offering, id__in=enrollment_ids)

        if action == "drop":
            updated = qs.update(status=Enrollment.DROPPED)
            messages.success(request, f"Updated {updated} enrollment(s) to Dropped.")
        elif action == "restore":
            updated = qs.update(status=Enrollment.ACTIVE)
            messages.success(request, f"Updated {updated} enrollment(s) to Active.")
        else:
            messages.error(request, "Invalid action.")

        redirect_url = reverse("admin_enrollment_bulk_status") + "?" + urlencode(
            {"offering": selected_offering.id, "q": q, "per_page": per_page}
        )
        return redirect(redirect_url)

    return render(
        request,
        "portals/admin/academics/enrollment_bulk_status.html",
        {
            "offerings": offerings,
            "selected_offering": selected_offering,
            "enrollments": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def year_create(request):
    if request.method == "POST":
        form = AcademicYearForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_academic_year_list")
    else:
        form = AcademicYearForm()
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Academic Year",
        form,
        "admin_academic_year_list",
    )


@admin_portal_required
def year_edit(request, pk: int):
    obj = get_object_or_404(AcademicYear, pk=pk)
    if request.method == "POST":
        form = AcademicYearForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_academic_year_list")
    else:
        form = AcademicYearForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Academic Year",
        form,
        "admin_academic_year_list",
    )


@admin_portal_required
def term_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = AcademicTerm.objects.select_related("year").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(year__name__icontains=q))
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/terms_list.html",
        {
            "terms": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def term_create(request):
    if request.method == "POST":
        form = AcademicTermForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_academic_term_list")
    else:
        form = AcademicTermForm()
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Academic Term",
        form,
        "admin_academic_term_list",
    )


@admin_portal_required
def term_edit(request, pk: int):
    obj = get_object_or_404(AcademicTerm, pk=pk)
    if request.method == "POST":
        form = AcademicTermForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_academic_term_list")
    else:
        form = AcademicTermForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Academic Term",
        form,
        "admin_academic_term_list",
    )


@admin_portal_required
def level_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Level.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/levels_list.html",
        {
            "levels": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def level_create(request):
    if request.method == "POST":
        form = LevelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_level_list")
    else:
        form = LevelForm()
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Level",
        form,
        "admin_level_list",
    )


@admin_portal_required
def level_edit(request, pk: int):
    obj = get_object_or_404(Level, pk=pk)
    if request.method == "POST":
        form = LevelForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_level_list")
    else:
        form = LevelForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Level",
        form,
        "admin_level_list",
    )


@admin_portal_required
def program_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Program.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/programs_list.html",
        {
            "programs": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def program_create(request):
    if request.method == "POST":
        form = ProgramForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_program_list")
    else:
        form = ProgramForm()
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Program",
        form,
        "admin_program_list",
    )


@admin_portal_required
def program_edit(request, pk: int):
    obj = get_object_or_404(Program, pk=pk)
    if request.method == "POST":
        form = ProgramForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_program_list")
    else:
        form = ProgramForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Program",
        form,
        "admin_program_list",
    )


@admin_portal_required
def classgroup_list(request):
    q = (request.GET.get("q") or "").strip()
    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)

    qs = ClassGroup.objects.select_related("campus", "level", "program").all()
    if campus_id:
        qs = qs.filter(campus_id=campus_id)
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(level__name__icontains=q)
            | Q(program__name__icontains=q)
        )
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/classgroups_list.html",
        {
            "classgroups": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def classgroup_create(request):
    current = get_current_campus(request)
    if request.method == "POST":
        form = ClassGroupForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.campus_id is None and current is not None:
                obj.campus = current
            obj.save()
            return redirect("admin_classgroup_list")
    else:
        form = ClassGroupForm()
        if current is not None:
            form.fields["campus"].initial = current
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Class Group",
        form,
        "admin_classgroup_list",
    )


@admin_portal_required
def classgroup_edit(request, pk: int):
    obj = get_object_or_404(ClassGroup, pk=pk)
    if request.method == "POST":
        form = ClassGroupForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_classgroup_list")
    else:
        form = ClassGroupForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Class Group",
        form,
        "admin_classgroup_list",
    )


@admin_portal_required
def course_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Course.objects.select_related("level", "program").all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(level__name__icontains=q)
            | Q(program__name__icontains=q)
        )
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/courses_list.html",
        {
            "courses": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def course_create(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_course_list")
    else:
        form = CourseForm()
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Course",
        form,
        "admin_course_list",
    )


@admin_portal_required
def course_edit(request, pk: int):
    obj = get_object_or_404(Course, pk=pk)
    if request.method == "POST":
        form = CourseForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_course_list")
    else:
        form = CourseForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Course",
        form,
        "admin_course_list",
    )


@admin_portal_required
def offering_list(request):
    q = (request.GET.get("q") or "").strip()
    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)

    qs = CourseOffering.objects.select_related(
        "campus",
        "course",
        "term",
        "term__year",
        "class_group",
        "teacher",
    ).all()
    if campus_id:
        qs = qs.filter(campus_id=campus_id)
    if q:
        qs = qs.filter(
            Q(course__name__icontains=q)
            | Q(course__code__icontains=q)
            | Q(term__name__icontains=q)
            | Q(term__year__name__icontains=q)
            | Q(class_group__name__icontains=q)
            | Q(teacher__first_name__icontains=q)
            | Q(teacher__last_name__icontains=q)
        )
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/offerings_list.html",
        {
            "offerings": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def offering_create(request):
    current = get_current_campus(request)
    if request.method == "POST":
        form = CourseOfferingForm(request.POST, campus=current)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.campus_id is None and current is not None:
                obj.campus = current
            obj.save()
            return redirect("admin_offering_list")
    else:
        form = CourseOfferingForm(campus=current)
        if current is not None:
            form.fields["campus"].initial = current
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Course Offering",
        form,
        "admin_offering_list",
    )


@admin_portal_required
def offering_edit(request, pk: int):
    obj = get_object_or_404(CourseOffering, pk=pk)
    if request.method == "POST":
        campus = obj.campus
        form = CourseOfferingForm(request.POST, instance=obj, campus=campus)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.save()
            return redirect("admin_offering_list")
    else:
        campus = obj.campus
        form = CourseOfferingForm(instance=obj, campus=campus)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Course Offering",
        form,
        "admin_offering_list",
    )


@admin_portal_required
def enrollment_list(request):
    q = (request.GET.get("q") or "").strip()
    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)
    qs = Enrollment.objects.select_related(
        "campus",
        "student",
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
    ).all()
    if campus_id:
        qs = qs.filter(campus_id=campus_id)
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(offering__course__name__icontains=q)
            | Q(offering__course__code__icontains=q)
            | Q(offering__term__name__icontains=q)
            | Q(offering__term__year__name__icontains=q)
        )
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/enrollments_list.html",
        {
            "enrollments": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def enrollment_create(request):
    current = get_current_campus(request)
    if request.method == "POST":
        form = EnrollmentForm(request.POST, campus=current)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.campus_id is None:
                if obj.offering_id and getattr(obj.offering, "campus_id", None):
                    obj.campus_id = obj.offering.campus_id
                elif obj.student_id and getattr(obj.student, "campus_id", None):
                    obj.campus_id = obj.student.campus_id
                elif current is not None:
                    obj.campus = current
            obj.save()
            return redirect("admin_enrollment_list")
    else:
        form = EnrollmentForm(campus=current)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Enrollment",
        form,
        "admin_enrollment_list",
    )


@admin_portal_required
def enrollment_edit(request, pk: int):
    obj = get_object_or_404(Enrollment, pk=pk)
    if request.method == "POST":
        campus = obj.campus
        form = EnrollmentForm(request.POST, instance=obj, campus=campus)
        if form.is_valid():
            saved = form.save(commit=False)
            if saved.campus_id is None:
                if saved.offering_id and getattr(saved.offering, "campus_id", None):
                    saved.campus_id = saved.offering.campus_id
                elif saved.student_id and getattr(saved.student, "campus_id", None):
                    saved.campus_id = saved.student.campus_id
            saved.save()
            return redirect("admin_enrollment_list")
    else:
        campus = obj.campus
        form = EnrollmentForm(instance=obj, campus=campus)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Enrollment",
        form,
        "admin_enrollment_list",
    )


@admin_portal_required
def enrollment_bulk(request):
    offering_id = request.GET.get("offering") or request.POST.get("offering")
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page") or request.POST.get("per_page")

    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)

    offerings = CourseOffering.objects.select_related(
        "course",
        "term",
        "term__year",
        "class_group",
        "teacher",
    ).all()
    if campus_id:
        offerings = offerings.filter(campus_id=campus_id)
    selected_offering = None
    if offering_id:
        selected_offering = offerings.filter(id=offering_id).first()

    students_qs = StudentProfile.objects.all()
    if campus_id:
        students_qs = students_qs.filter(campus_id=campus_id)
    if q:
        students_qs = students_qs.filter(
            Q(student_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    per_page = _parse_per_page(request, raw=per_page_raw)
    page_number = request.GET.get("page") or 1
    paginator = Paginator(students_qs, per_page)
    page_obj = paginator.get_page(page_number)

    if request.method == "POST":
        if not selected_offering:
            messages.error(request, "Please select an offering.")
            return redirect(reverse("admin_enrollment_bulk"))

        student_ids = request.POST.getlist("student_ids")
        created = 0
        skipped = 0
        for sid in student_ids:
            obj, was_created = Enrollment.objects.get_or_create(
                offering=selected_offering,
                student_id=sid,
                defaults={
                    "status": Enrollment.ACTIVE,
                    "campus_id": getattr(selected_offering, "campus_id", None) or campus_id,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        messages.success(
            request,
            f"Bulk enrollment complete. Created: {created}. Skipped (already enrolled): {skipped}.",
        )

        redirect_url = reverse("admin_enrollment_bulk") + "?" + urlencode(
            {"offering": selected_offering.id, "q": q, "per_page": per_page}
        )
        return redirect(redirect_url)

    return render(
        request,
        "portals/admin/academics/enrollment_bulk.html",
        {
            "offerings": offerings,
            "selected_offering": selected_offering,
            "students": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def grading_scale_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = GradingScale.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/grading_scales_list.html",
        {
            "grading_scales": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def grading_scale_create(request):
    if request.method == "POST":
        form = GradingScaleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Grading scale created successfully.")
            return redirect("admin_grading_scale_list")
    else:
        form = GradingScaleForm()
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Grading Scale",
        form,
        "admin_grading_scale_list",
    )


@admin_portal_required
def grading_scale_edit(request, pk: int):
    obj = get_object_or_404(GradingScale, pk=pk)
    if request.method == "POST":
        form = GradingScaleForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Grading scale updated successfully.")
            return redirect("admin_grading_scale_list")
    else:
        form = GradingScaleForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Grading Scale",
        form,
        "admin_grading_scale_list",
    )


@admin_portal_required
def grading_scale_detail(request, pk: int):
    scale = get_object_or_404(GradingScale.objects.prefetch_related('ranges'), pk=pk)
    
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "set_default":
            with transaction.atomic():
                GradingScale.objects.update(is_default=False)
                scale.is_default = True
                scale.save(update_fields=["is_default"])
            messages.success(request, f"Set '{scale.name}' as default grading scale.")
            return redirect("admin_grading_scale_detail", pk=pk)
    
    return render(
        request,
        "portals/admin/academics/grading_scale_detail.html",
        {
            "scale": scale,
            "ranges": scale.ranges.all(),
        },
    )


@admin_portal_required
def grade_range_create(request, scale_id: int):
    scale = get_object_or_404(GradingScale, pk=scale_id)
    if request.method == "POST":
        form = GradeRangeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Grade range added successfully.")
            return redirect("admin_grading_scale_detail", pk=scale_id)
    else:
        form = GradeRangeForm(initial={"scale": scale})
    return render(
        request,
        "portals/admin/academics/form.html",
        {
            "title": f"Add Grade Range to {scale.name}",
            "form": form,
            "list_url_name": "admin_grading_scale_detail",
            "list_url_pk": scale_id,
        },
    )


@admin_portal_required
def grade_range_edit(request, pk: int):
    obj = get_object_or_404(GradeRange, pk=pk)
    scale_id = obj.scale_id
    if request.method == "POST":
        form = GradeRangeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Grade range updated successfully.")
            return redirect("admin_grading_scale_detail", pk=scale_id)
    else:
        form = GradeRangeForm(instance=obj)
    return render(
        request,
        "portals/admin/academics/form.html",
        {
            "title": "Edit Grade Range",
            "form": form,
            "list_url_name": "admin_grading_scale_detail",
            "list_url_pk": scale_id,
        },
    )


@admin_portal_required
def stream_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Stream.objects.select_related("class_group", "class_teacher").all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(class_group__name__icontains=q)
            | Q(room__icontains=q)
        )
    page_obj, per_page = _paginate_queryset(request, qs)
    return render(
        request,
        "portals/admin/academics/streams_list.html",
        {
            "streams": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@admin_portal_required
def stream_create(request):
    if request.method == "POST":
        form = StreamForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Stream created successfully.")
            return redirect("admin_stream_list")
    else:
        form = StreamForm()
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Stream",
        form,
        "admin_stream_list",
    )


@admin_portal_required
def stream_edit(request, pk: int):
    obj = get_object_or_404(Stream, pk=pk)
    if request.method == "POST":
        form = StreamForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Stream updated successfully.")
            return redirect("admin_stream_list")
    else:
        form = StreamForm(instance=obj)
    return _simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Stream",
        form,
        "admin_stream_list",
    )


@admin_portal_required
def report_card_view(request, student_id: int, term_id: int):
    from .reports import ReportCard
    
    try:
        report_card = ReportCard(student_id, term_id)
        data = report_card.to_dict()
        
        return render(
            request,
            "portals/admin/academics/report_card.html",
            {
                "report_card": data,
                "student": report_card.student,
                "term": report_card.term,
            },
        )
    except Exception as e:
        messages.error(request, f"Error generating report card: {str(e)}")
        return redirect("admin_student_list")


@admin_portal_required
def term_report_cards(request, term_id: int):
    from .reports import generate_class_report_cards
    
    term = get_object_or_404(AcademicTerm, pk=term_id)
    stream_id = request.GET.get("stream")
    class_group_id = request.GET.get("class_group")
    q = (request.GET.get("q") or "").strip()
    
    streams = Stream.objects.select_related("class_group").filter(is_active=True)
    class_groups = ClassGroup.objects.filter(is_active=True)
    
    report_cards = generate_class_report_cards(
        term_id,
        stream_id=int(stream_id) if stream_id else None,
        class_group_id=int(class_group_id) if class_group_id else None,
    )
    rows = []
    averages = []
    for report_card in report_cards:
        student = report_card.student
        if q and q.lower() not in f"{student.first_name} {student.last_name} {student.student_id}".lower():
            continue
        summary = report_card.get_summary()
        ranking = report_card.get_ranking() or {}
        average = summary.get("average")
        if average is not None:
            averages.append(average)
        rows.append(
            {
                "id": student.id,
                "name": str(student),
                "student_id": student.student_id,
                "stream": student.stream,
                "average": average,
                "rank": ranking.get("rank"),
                "total": ranking.get("total"),
            }
        )
    
    return render(
        request,
        "portals/admin/academics/term_report_cards.html",
        {
            "term": term,
            "students": rows,
            "total_students": len(rows),
            "generated_count": len(rows),
            "pending_count": 0,
            "average_gpa": (sum(averages) / len(averages)) if averages else None,
            "streams": streams,
            "class_groups": class_groups,
            "q": q,
            "selected_stream": stream_id or "",
            "selected_stream_id": int(stream_id) if stream_id else None,
            "selected_class_group_id": int(class_group_id) if class_group_id else None,
        },
    )
