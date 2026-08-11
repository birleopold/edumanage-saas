from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import set_current_campus
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.portals.role_navigation import is_global_admin_user
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from . import views as legacy_views
from .forms import ClassGroupForm, CourseOfferingForm, EnrollmentForm, StreamForm
from .models import AcademicTerm, ClassGroup, CourseOffering, Enrollment, Stream
from .reports import ReportCard


def _campus_admin_scope(request):
    """Return the mandatory campus scope for a Campus Admin.

    Tenant-wide Admin/Principal users intentionally return ``None`` so their
    existing multi-campus workflows continue unchanged. A Campus Admin with no
    valid UserRole campus assignment fails closed instead of becoming global.
    """

    if is_global_admin_user(request.user):
        return None
    if request.user.has_role(Role.CAMPUS_ADMIN):
        scope = get_user_campus_scope(request.user)
        if scope is None:
            raise PermissionDenied("Your Campus Admin account has no active campus assignment.")
        set_current_campus(request, scope)
        return scope
    return None


def _delegate_if_global(request, legacy_view, *args, **kwargs):
    scope = _campus_admin_scope(request)
    if scope is None:
        return legacy_view(request, *args, **kwargs), None
    return None, scope


def _campus_choices(scope):
    return Campus.objects.filter(pk=scope.pk)


def _lock_campus_field(form, scope):
    if "campus" not in form.fields:
        return
    form.fields["campus"].queryset = _campus_choices(scope)
    form.fields["campus"].initial = scope
    form.fields["campus"].required = True
    form.fields["campus"].disabled = True


def _paginate(request, qs, raw_per_page=None):
    per_page = legacy_views._parse_per_page(request, raw=raw_per_page)
    page_obj = Paginator(qs, per_page).get_page(request.GET.get("page") or 1)
    return page_obj, per_page


@admin_portal_required
def classgroup_list(request):
    delegated, scope = _delegate_if_global(request, legacy_views.classgroup_list)
    if delegated is not None:
        return delegated

    q = (request.GET.get("q") or "").strip()
    qs = ClassGroup.objects.filter(campus=scope).select_related("campus", "level", "program")
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(level__name__icontains=q)
            | Q(program__name__icontains=q)
        )
    page_obj, per_page = _paginate(request, qs)
    return render(
        request,
        "portals/admin/academics/classgroups_list.html",
        {
            "classgroups": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": _campus_choices(scope),
            "selected_campus_id": scope.pk,
        },
    )


@admin_portal_required
def classgroup_create(request):
    delegated, scope = _delegate_if_global(request, legacy_views.classgroup_create)
    if delegated is not None:
        return delegated

    form = ClassGroupForm(request.POST or None, initial={"campus": scope})
    _lock_campus_field(form, scope)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.campus = scope
        obj.save()
        messages.success(request, "Class group created for your campus.")
        return redirect("admin_classgroup_list")
    return legacy_views._simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Class Group",
        form,
        "admin_classgroup_list",
    )


@admin_portal_required
def classgroup_edit(request, pk):
    delegated, scope = _delegate_if_global(request, legacy_views.classgroup_edit, pk)
    if delegated is not None:
        return delegated

    obj = get_object_or_404(ClassGroup, pk=pk, campus=scope)
    form = ClassGroupForm(request.POST or None, instance=obj)
    _lock_campus_field(form, scope)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.campus = scope
        saved.save()
        messages.success(request, "Class group updated.")
        return redirect("admin_classgroup_list")
    return legacy_views._simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Class Group",
        form,
        "admin_classgroup_list",
    )


@admin_portal_required
def offering_list(request):
    delegated, scope = _delegate_if_global(request, legacy_views.offering_list)
    if delegated is not None:
        return delegated

    q = (request.GET.get("q") or "").strip()
    qs = CourseOffering.objects.filter(campus=scope).select_related(
        "campus", "course", "term", "term__year", "class_group", "teacher"
    )
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
    page_obj, per_page = _paginate(request, qs)
    return render(
        request,
        "portals/admin/academics/offerings_list.html",
        {
            "offerings": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": _campus_choices(scope),
            "selected_campus_id": scope.pk,
        },
    )


def _offering_form(data, *, scope, instance=None):
    form = CourseOfferingForm(data, instance=instance, campus=scope)
    _lock_campus_field(form, scope)
    return form


@admin_portal_required
def offering_create(request):
    delegated, scope = _delegate_if_global(request, legacy_views.offering_create)
    if delegated is not None:
        return delegated

    form = _offering_form(request.POST or None, scope=scope)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.campus = scope
        obj.save()
        messages.success(request, "Course offering created for your campus.")
        return redirect("admin_offering_list")
    return legacy_views._simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Course Offering",
        form,
        "admin_offering_list",
    )


@admin_portal_required
def offering_edit(request, pk):
    delegated, scope = _delegate_if_global(request, legacy_views.offering_edit, pk)
    if delegated is not None:
        return delegated

    obj = get_object_or_404(CourseOffering, pk=pk, campus=scope)
    form = _offering_form(request.POST or None, scope=scope, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.campus = scope
        saved.save()
        messages.success(request, "Course offering updated.")
        return redirect("admin_offering_list")
    return legacy_views._simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Course Offering",
        form,
        "admin_offering_list",
    )


@admin_portal_required
def enrollment_list(request):
    delegated, scope = _delegate_if_global(request, legacy_views.enrollment_list)
    if delegated is not None:
        return delegated

    q = (request.GET.get("q") or "").strip()
    qs = Enrollment.objects.filter(campus=scope).select_related(
        "campus", "student", "offering", "offering__course", "offering__term", "offering__term__year"
    )
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
    page_obj, per_page = _paginate(request, qs)
    return render(
        request,
        "portals/admin/academics/enrollments_list.html",
        {
            "enrollments": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": _campus_choices(scope),
            "selected_campus_id": scope.pk,
        },
    )


def _enrollment_form(data, *, scope, instance=None):
    return EnrollmentForm(data, instance=instance, campus=scope)


@admin_portal_required
def enrollment_create(request):
    delegated, scope = _delegate_if_global(request, legacy_views.enrollment_create)
    if delegated is not None:
        return delegated

    form = _enrollment_form(request.POST or None, scope=scope)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.campus = scope
        obj.save()
        messages.success(request, "Enrollment created for your campus.")
        return redirect("admin_enrollment_list")
    return legacy_views._simple_form(
        request,
        "portals/admin/academics/form.html",
        "Add Enrollment",
        form,
        "admin_enrollment_list",
    )


@admin_portal_required
def enrollment_edit(request, pk):
    delegated, scope = _delegate_if_global(request, legacy_views.enrollment_edit, pk)
    if delegated is not None:
        return delegated

    obj = get_object_or_404(Enrollment, pk=pk, campus=scope)
    form = _enrollment_form(request.POST or None, scope=scope, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.campus = scope
        saved.save()
        messages.success(request, "Enrollment updated.")
        return redirect("admin_enrollment_list")
    return legacy_views._simple_form(
        request,
        "portals/admin/academics/form.html",
        "Edit Enrollment",
        form,
        "admin_enrollment_list",
    )


@admin_portal_required
def enrollment_bulk(request):
    delegated, scope = _delegate_if_global(request, legacy_views.enrollment_bulk)
    if delegated is not None:
        return delegated

    offering_id = request.GET.get("offering") or request.POST.get("offering")
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page") or request.POST.get("per_page")
    offerings = CourseOffering.objects.filter(campus=scope).select_related(
        "course", "term", "term__year", "class_group", "teacher"
    )
    selected_offering = offerings.filter(pk=offering_id).first() if offering_id else None
    students_qs = StudentProfile.objects.filter(campus=scope, is_active=True).order_by("last_name", "first_name")
    if q:
        students_qs = students_qs.filter(
            Q(student_id__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )
    per_page = legacy_views._parse_per_page(request, raw=per_page_raw)
    page_obj = Paginator(students_qs, per_page).get_page(request.GET.get("page") or 1)

    if request.method == "POST":
        if not selected_offering:
            messages.error(request, "Select an offering from your campus.")
            return redirect("admin_enrollment_bulk")
        raw_ids = request.POST.getlist("student_ids")
        try:
            selected_ids = {int(value) for value in raw_ids}
        except (TypeError, ValueError):
            selected_ids = set()
        allowed_ids = set(students_qs.filter(pk__in=selected_ids).values_list("pk", flat=True))
        if not selected_ids:
            messages.warning(request, "Select at least one learner.")
        elif allowed_ids != selected_ids:
            messages.error(request, "One or more selected learners are outside your campus. No enrollments were created.")
        else:
            created = 0
            skipped = 0
            with transaction.atomic():
                for student_id in sorted(selected_ids):
                    _obj, was_created = Enrollment.objects.get_or_create(
                        offering=selected_offering,
                        student_id=student_id,
                        defaults={"status": Enrollment.ACTIVE, "campus": scope},
                    )
                    created += int(was_created)
                    skipped += int(not was_created)
            messages.success(request, f"Bulk enrollment complete. Created: {created}. Skipped: {skipped}.")
        params = {"offering": selected_offering.pk, "q": q, "per_page": per_page}
        return redirect(reverse("admin_enrollment_bulk") + "?" + urlencode(params))

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
            "campuses": _campus_choices(scope),
            "selected_campus_id": scope.pk,
        },
    )


@admin_portal_required
def enrollment_bulk_status(request):
    delegated, scope = _delegate_if_global(request, legacy_views.enrollment_bulk_status)
    if delegated is not None:
        return delegated

    offering_id = request.GET.get("offering") or request.POST.get("offering")
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page") or request.POST.get("per_page")
    offerings = CourseOffering.objects.filter(campus=scope).select_related(
        "course", "term", "term__year", "class_group", "teacher"
    )
    selected_offering = offerings.filter(pk=offering_id).first() if offering_id else None
    enrollments_qs = Enrollment.objects.filter(campus=scope).select_related(
        "student", "offering", "offering__course", "offering__term", "offering__term__year"
    )
    enrollments_qs = enrollments_qs.filter(offering=selected_offering) if selected_offering else enrollments_qs.none()
    if q:
        enrollments_qs = enrollments_qs.filter(
            Q(student__student_id__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
        )
    per_page = legacy_views._parse_per_page(request, raw=per_page_raw)
    page_obj = Paginator(enrollments_qs, per_page).get_page(request.GET.get("page") or 1)

    if request.method == "POST":
        if not selected_offering:
            messages.error(request, "Select an offering from your campus.")
            return redirect("admin_enrollment_bulk_status")
        ids = request.POST.getlist("enrollment_ids")
        qs = enrollments_qs.filter(pk__in=ids)
        action = request.POST.get("action")
        if action == "drop":
            updated = qs.update(status=Enrollment.DROPPED)
            messages.success(request, f"Updated {updated} enrollment(s) to Dropped.")
        elif action == "restore":
            updated = qs.update(status=Enrollment.ACTIVE)
            messages.success(request, f"Updated {updated} enrollment(s) to Active.")
        else:
            messages.error(request, "Invalid action.")
        params = {"offering": selected_offering.pk, "q": q, "per_page": per_page}
        return redirect(reverse("admin_enrollment_bulk_status") + "?" + urlencode(params))

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


def _stream_form(data, *, scope, instance=None):
    form = StreamForm(data, instance=instance)
    form.fields["class_group"].queryset = ClassGroup.objects.filter(campus=scope, is_active=True)
    form.fields["class_teacher"].queryset = TeacherProfile.objects.filter(campus=scope, is_active=True)
    return form


@admin_portal_required
def stream_list(request):
    delegated, scope = _delegate_if_global(request, legacy_views.stream_list)
    if delegated is not None:
        return delegated

    q = (request.GET.get("q") or "").strip()
    qs = Stream.objects.filter(class_group__campus=scope).select_related("class_group", "class_teacher")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(class_group__name__icontains=q) | Q(room__icontains=q))
    page_obj, per_page = _paginate(request, qs)
    return render(
        request,
        "portals/admin/academics/streams_list.html",
        {"streams": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def stream_create(request):
    delegated, scope = _delegate_if_global(request, legacy_views.stream_create)
    if delegated is not None:
        return delegated

    form = _stream_form(request.POST or None, scope=scope)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Stream created for your campus.")
        return redirect("admin_stream_list")
    return legacy_views._simple_form(
        request, "portals/admin/academics/form.html", "Add Stream", form, "admin_stream_list"
    )


@admin_portal_required
def stream_edit(request, pk):
    delegated, scope = _delegate_if_global(request, legacy_views.stream_edit, pk)
    if delegated is not None:
        return delegated

    obj = get_object_or_404(Stream, pk=pk, class_group__campus=scope)
    form = _stream_form(request.POST or None, scope=scope, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Stream updated.")
        return redirect("admin_stream_list")
    return legacy_views._simple_form(
        request, "portals/admin/academics/form.html", "Edit Stream", form, "admin_stream_list"
    )


@admin_portal_required
def report_card_view(request, student_id, term_id):
    delegated, scope = _delegate_if_global(request, legacy_views.report_card_view, student_id, term_id)
    if delegated is not None:
        return delegated

    student = get_object_or_404(StudentProfile, pk=student_id, campus=scope)
    term = get_object_or_404(AcademicTerm, pk=term_id)
    report_card = ReportCard(student.pk, term.pk)
    return render(
        request,
        "portals/admin/academics/report_card.html",
        {"report_card": report_card.to_dict(), "student": student, "term": term},
    )


@admin_portal_required
def term_report_cards(request, term_id):
    delegated, scope = _delegate_if_global(request, legacy_views.term_report_cards, term_id)
    if delegated is not None:
        return delegated

    term = get_object_or_404(AcademicTerm, pk=term_id)
    stream_id = request.GET.get("stream")
    class_group_id = request.GET.get("class_group")
    q = (request.GET.get("q") or "").strip()
    streams = Stream.objects.filter(class_group__campus=scope, is_active=True).select_related("class_group")
    class_groups = ClassGroup.objects.filter(campus=scope, is_active=True)

    selected_stream = None
    selected_class_group = None
    if stream_id:
        selected_stream = get_object_or_404(streams, pk=stream_id)
    if class_group_id:
        selected_class_group = get_object_or_404(class_groups, pk=class_group_id)

    students_qs = StudentProfile.objects.filter(
        campus=scope,
        is_active=True,
        enrollment__offering__term=term,
        enrollment__status=Enrollment.ACTIVE,
    ).distinct().order_by("last_name", "first_name")
    if selected_stream:
        students_qs = students_qs.filter(stream=selected_stream)
    elif selected_class_group:
        students_qs = students_qs.filter(stream__class_group=selected_class_group)
    if q:
        students_qs = students_qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(student_id__icontains=q)
        )

    rows = []
    averages = []
    for student in students_qs:
        report_card = ReportCard(student.pk, term.pk)
        summary = report_card.get_summary()
        ranking = report_card.get_ranking() or {}
        average = summary.get("average")
        if average is not None:
            averages.append(average)
        rows.append(
            {
                "id": student.pk,
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
            "selected_stream_id": selected_stream.pk if selected_stream else None,
            "selected_class_group_id": selected_class_group.pk if selected_class_group else None,
        },
    )
