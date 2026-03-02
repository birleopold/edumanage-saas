import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.tenant.academics.models import CourseOffering, Enrollment
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

from .models import AttendanceEntry, AttendanceSession


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
def attendance_home(request):
    _apply_campus_selection_from_request(request)

    teacher = TeacherProfile.objects.filter(user=request.user).first()
    campuses = _campus_queryset()
    current_campus = get_current_campus(request)
    selected_campus_id = current_campus.id if current_campus else None

    offerings = CourseOffering.objects.none()
    if teacher:
        offerings = CourseOffering.objects.select_related(
            "course",
            "term",
            "term__year",
            "class_group",
        ).filter(teacher=teacher)

        if selected_campus_id:
            offerings = offerings.filter(campus_id=selected_campus_id)

    return render(
        request,
        "portals/teacher/attendance/home.html",
        {
            "teacher": teacher,
            "offerings": offerings,
            "campuses": campuses,
            "selected_campus_id": selected_campus_id,
        },
    )


@role_required(Role.TEACHER)
def attendance_take(request):
    _apply_campus_selection_from_request(request)

    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    campuses = _campus_queryset()
    current_campus = get_current_campus(request)
    selected_campus_id = current_campus.id if current_campus else None

    offering_id = request.GET.get("offering") or request.POST.get("offering")
    date_raw = request.GET.get("date") or request.POST.get("date")
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()

    try:
        selected_date = (
            datetime.date.fromisoformat(date_raw) if date_raw else datetime.date.today()
        )
    except ValueError:
        selected_date = datetime.date.today()

    offerings = CourseOffering.objects.select_related(
        "course",
        "term",
        "term__year",
        "class_group",
    ).filter(teacher=teacher)

    if selected_campus_id:
        offerings = offerings.filter(campus_id=selected_campus_id)

    selected_offering = None
    if offering_id:
        selected_offering = offerings.filter(id=offering_id).first()

    enrollments_qs = Enrollment.objects.select_related("student").filter(status=Enrollment.ACTIVE)
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

    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1
    paginator = Paginator(enrollments_qs, per_page)
    page_obj = paginator.get_page(page_number)

    session = None
    existing_entries = {}
    if selected_offering:
        session = AttendanceSession.objects.filter(
            offering=selected_offering,
            date=selected_date,
        ).first()
        if session:
            existing_entries = {
                e.student_id: e
                for e in AttendanceEntry.objects.filter(session=session).select_related("student")
            }

    if request.method == "POST":
        if not selected_offering:
            messages.error(request, "Please select an offering.")
            return redirect(reverse("teacher_attendance_take"))

        with transaction.atomic():
            session, _created = AttendanceSession.objects.get_or_create(
                offering=selected_offering,
                date=selected_date,
                defaults={"taken_by": teacher},
            )
            if session.taken_by_id is None:
                session.taken_by = teacher
                session.save(update_fields=["taken_by"])

            student_ids = request.POST.getlist("student_ids")
            updated = 0
            for sid in student_ids:
                status = request.POST.get(f"status_{sid}") or AttendanceEntry.PRESENT
                note = request.POST.get(f"note_{sid}") or ""
                AttendanceEntry.objects.update_or_create(
                    session=session,
                    student_id=sid,
                    defaults={"status": status, "note": note},
                )
                updated += 1

        messages.success(request, f"Attendance saved for {updated} student(s).")

        campus_qs = f"&campus={selected_campus_id}" if selected_campus_id else "&campus="
        return redirect(
            reverse("teacher_attendance_take")
            + f"?offering={selected_offering.id}&date={selected_date.isoformat()}" + campus_qs
        )

    return render(
        request,
        "portals/teacher/attendance/take.html",
        {
            "teacher": teacher,
            "offerings": offerings,
            "selected_offering": selected_offering,
            "selected_date": selected_date,
            "enrollments": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "existing_entries": existing_entries,
            "STATUS_CHOICES": AttendanceEntry.STATUS_CHOICES,
            "campuses": campuses,
            "selected_campus_id": selected_campus_id,
        },
    )
