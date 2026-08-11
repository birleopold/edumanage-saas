from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, set_current_campus
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.portals.role_navigation import is_global_admin_user
from apps.tenant.reports.models import TermReportRemark
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import AcademicTerm, Enrollment, Stream


def _campus_context(request):
    """Return (campus, can_edit_head_comment) for the current admin user."""
    if not is_global_admin_user(request.user) and request.user.has_role(Role.CAMPUS_ADMIN):
        campus = get_user_campus_scope(request.user)
        if campus is None:
            raise PermissionDenied("Your Campus Admin account has no active campus assignment.")
        set_current_campus(request, campus)
        return campus, False

    campus = get_current_campus(request)
    requested = request.GET.get("campus") if request.method == "GET" else request.POST.get("campus")
    if requested:
        try:
            requested_id = int(requested)
        except (TypeError, ValueError):
            requested_id = None
        if requested_id:
            chosen = Campus.objects.filter(pk=requested_id, is_active=True).first()
            if chosen:
                campus = chosen
                set_current_campus(request, chosen)
    return campus, bool(is_global_admin_user(request.user))


def _redirect_url(term, *, campus, stream_id, q, page):
    params = {}
    if campus:
        params["campus"] = campus.pk
    if stream_id:
        params["stream"] = stream_id
    if q:
        params["q"] = q
    if page:
        params["page"] = page
    base = reverse("admin_term_report_remarks", args=[term.pk])
    return base + ("?" + urlencode(params) if params else "")


@admin_portal_required
def term_report_remarks(request, term_id):
    term = get_object_or_404(AcademicTerm, pk=term_id)
    campus, can_edit_head = _campus_context(request)
    stream_id = request.GET.get("stream") if request.method == "GET" else request.POST.get("stream")
    raw_q = request.GET.get("q") if request.method == "GET" else request.POST.get("q")
    q = (raw_q or "").strip()
    page_number = request.GET.get("page") if request.method == "GET" else request.POST.get("page")

    students = StudentProfile.objects.filter(
        is_active=True,
        enrollment__offering__term=term,
        enrollment__status=Enrollment.ACTIVE,
    ).select_related("campus", "stream", "stream__class_group").distinct().order_by("last_name", "first_name")
    streams = Stream.objects.filter(is_active=True).select_related("class_group", "class_group__campus")
    campuses = Campus.objects.filter(is_active=True).order_by("name")

    if campus:
        students = students.filter(campus=campus)
        streams = streams.filter(class_group__campus=campus)
        campuses = campuses.filter(pk=campus.pk) if not can_edit_head else campuses

    selected_stream = None
    if stream_id:
        selected_stream = streams.filter(pk=stream_id).first()
        if selected_stream:
            students = students.filter(stream=selected_stream)
        else:
            stream_id = ""

    if q:
        students = students.filter(
            Q(student_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    paginator = Paginator(students, 25)
    page_obj = paginator.get_page(page_number or 1)
    visible_students = list(page_obj.object_list)
    visible_ids = {student.pk for student in visible_students}

    if request.method == "POST":
        posted_ids = set()
        for raw in request.POST.getlist("student_ids"):
            try:
                posted_ids.add(int(raw))
            except (TypeError, ValueError):
                continue

        if not posted_ids:
            messages.warning(request, "There are no learner remarks to save on this page.")
        elif posted_ids != visible_ids:
            messages.error(request, "One or more learners are outside the current campus/filter scope. No remarks were changed.")
        else:
            existing = {
                remark.student_id: remark
                for remark in TermReportRemark.objects.filter(term=term, student_id__in=posted_ids)
            }
            changed = 0
            with transaction.atomic():
                for student in visible_students:
                    teacher_comment = (request.POST.get(f"class_teacher_comment_{student.pk}") or "").strip()
                    submitted_head_comment = (request.POST.get(f"head_comment_{student.pk}") or "").strip()
                    remark = existing.get(student.pk)
                    head_comment = submitted_head_comment if can_edit_head else (remark.head_comment if remark else "")
                    if remark is None:
                        if not teacher_comment and not head_comment:
                            continue
                        remark = TermReportRemark(student=student, term=term, campus=student.campus)
                    if (
                        remark.class_teacher_comment == teacher_comment
                        and remark.head_comment == head_comment
                        and remark.campus_id == student.campus_id
                    ):
                        continue
                    remark.class_teacher_comment = teacher_comment
                    remark.head_comment = head_comment
                    remark.campus = student.campus
                    remark.updated_by = request.user
                    remark.save()
                    changed += 1
            messages.success(request, f"Saved report remarks for {changed} learner(s).")

        return redirect(
            _redirect_url(
                term,
                campus=campus,
                stream_id=stream_id,
                q=q,
                page=page_number,
            )
        )

    remarks = {
        remark.student_id: remark
        for remark in TermReportRemark.objects.filter(term=term, student_id__in=visible_ids)
    }
    rows = [{"student": student, "remark": remarks.get(student.pk)} for student in visible_students]

    return render(
        request,
        "portals/admin/academics/term_report_remarks.html",
        {
            "term": term,
            "rows": rows,
            "page_obj": page_obj,
            "streams": streams,
            "campuses": campuses,
            "selected_campus_id": campus.pk if campus else None,
            "selected_stream_id": selected_stream.pk if selected_stream else None,
            "q": q,
            "can_edit_head": can_edit_head,
        },
    )
