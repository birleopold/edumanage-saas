from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from apps.tenant.assessments.parent_session import PIN_SESSION_KEY as PARENT_RESULTS_PIN_SESSION_KEY
from apps.tenant.orgsettings.services import (
    campus_queryset,
    get_current_campus,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)

from apps.tenant.academics.models import AcademicTerm, AcademicYear, CourseOffering, Enrollment
from apps.tenant.announcements.models import Announcement
from apps.tenant.assessments.models import AssessmentScore
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.coursework.models import Assignment, AssignmentSubmission
from apps.tenant.discipline.models import Incident
from apps.tenant.documents.models import Document
from apps.tenant.finance.models import Invoice
from apps.tenant.finance.services import filter_invoices_outstanding, filter_invoices_overdue
from apps.tenant.grievances.models import Grievance
from apps.tenant.parents.forms import ParentResultsPinSelfServiceForm
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.polls.portal_services import polls_for_user
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.timetable.models import TimetableEntry
from apps.tenant.users.models import Role

from .campus_permissions import get_user_campus_scope
from .experience_services import build_school_health_score, school_setup_progress
from .permissions import admin_portal_required, role_required


_TIMETABLE_WEEKDAY_CODES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _poll_items(request):
    try:
        return list(polls_for_user(request)[:3])
    except Exception:
        return []


def _teacher_daily_workflow(teacher):
    today = timezone.localdate()
    if not teacher:
        return {
            "today": today,
            "cards": [],
            "announcements": [],
            "ready_count": 0,
            "total": 0,
        }

    offerings = CourseOffering.objects.filter(teacher=teacher, is_active=True)
    weekday_code = _TIMETABLE_WEEKDAY_CODES[today.weekday()]

    timetable_count = TimetableEntry.objects.filter(
        offering__in=offerings,
        weekday=weekday_code,
        is_active=True,
    ).count()

    attendance_count = AttendanceSession.objects.filter(
        offering__in=offerings,
        date=today,
    ).count()
    unmarked_attendance_count = max(offerings.count() - attendance_count, 0)
    pending_submissions_count = AssignmentSubmission.objects.filter(
        assignment__offering__in=offerings,
        submitted_at__isnull=False,
        score__isnull=True,
    ).count()
    active_assignments_count = Assignment.objects.filter(
        offering__in=offerings,
        is_active=True,
        publish_at__lte=timezone.now(),
    ).count()
    open_incidents_count = Incident.objects.filter(
        reported_by=teacher,
        status=Incident.OPEN,
    ).count()
    announcements = list(
        Announcement.objects.filter(is_active=True)
        .filter(Q(audience=Announcement.ALL) | Q(audience=Announcement.TEACHERS))
        .order_by("-is_urgent", "-created_at")[:3]
    )

    cards = [
        {
            "key": "timetable",
            "title": "Timetable",
            "metric": timetable_count,
            "detail": "lesson(s) scheduled today",
            "url": reverse("teacher_timetable"),
            "icon": "ph-calendar",
            "tone": "blue",
            "ready": timetable_count > 0,
        },
        {
            "key": "attendance",
            "title": "Attendance",
            "metric": unmarked_attendance_count,
            "detail": "active class(es) still need roll call",
            "url": reverse("teacher_roll_call"),
            "icon": "ph-calendar-check",
            "tone": "green",
            "ready": unmarked_attendance_count == 0 and offerings.exists(),
        },
        {
            "key": "coursework",
            "title": "Coursework",
            "metric": active_assignments_count,
            "detail": "active assignment(s)",
            "url": reverse("teacher_coursework_home"),
            "icon": "ph-notebook",
            "tone": "purple",
            "ready": active_assignments_count > 0,
        },
        {
            "key": "grading",
            "title": "Grading",
            "metric": pending_submissions_count,
            "detail": "submission(s) awaiting marks",
            "url": reverse("teacher_coursework_home"),
            "icon": "ph-exam",
            "tone": "indigo",
            "ready": pending_submissions_count == 0,
        },
        {
            "key": "incidents",
            "title": "Incidents",
            "metric": open_incidents_count,
            "detail": "open report(s) from you",
            "url": reverse("teacher_incidents_list"),
            "icon": "ph-warning-circle",
            "tone": "amber",
            "ready": open_incidents_count == 0,
        },
        {
            "key": "announcements",
            "title": "Announcements",
            "metric": len(announcements),
            "detail": "recent notice(s)",
            "url": reverse("teacher_announcements_list"),
            "icon": "ph-megaphone",
            "tone": "pink",
            "ready": True,
        },
    ]
    return {
        "today": today,
        "cards": cards,
        "announcements": announcements,
        "ready_count": sum(1 for card in cards if card["ready"]),
        "total": len(cards),
    }


def _parent_daily_workflow(parent_profile, links):
    today = timezone.localdate()
    students = [link.student for link in links]
    student_ids = [student.id for student in students]
    if not parent_profile:
        return {
            "today": today,
            "cards": [],
            "announcements": [],
            "ready_count": 0,
            "total": 0,
        }

    invoices = Invoice.objects.filter(student_id__in=student_ids)
    outstanding_count = filter_invoices_outstanding(invoices).count()
    attendance_count = AttendanceEntry.objects.filter(student_id__in=student_ids).count()
    published_scores_count = AssessmentScore.objects.filter(
        student_id__in=student_ids,
        assessment__is_published=True,
    ).count()
    announcements = list(
        Announcement.objects.filter(is_active=True)
        .filter(Q(audience=Announcement.ALL) | Q(audience=Announcement.PARENTS))
        .order_by("-is_urgent", "-created_at")[:3]
    )
    documents_qs = Document.objects.filter(is_active=True).filter(
        Q(audience=Document.ALL) | Q(audience=Document.PARENTS)
    )
    documents = list(documents_qs.order_by("-created_at")[:3])
    document_count = documents_qs.count()
    preferences_ready = (
        bool(parent_profile.communication_consent_updated_at)
        and (
            parent_profile.allow_sms_alerts
            or parent_profile.allow_whatsapp_alerts
            or parent_profile.digest_enabled
        )
    )

    cards = [
        {
            "key": "fees",
            "title": "Fees",
            "metric": outstanding_count,
            "detail": "invoice(s) with balance to review",
            "url": reverse("parent_invoices_list"),
            "icon": "ph-wallet",
            "ready": outstanding_count == 0,
        },
        {
            "key": "attendance",
            "title": "Attendance",
            "metric": attendance_count,
            "detail": "attendance record(s) available",
            "url": reverse("parent_attendance_home"),
            "icon": "ph-calendar-check",
            "ready": attendance_count > 0,
        },
        {
            "key": "report_cards",
            "title": "Report Cards",
            "metric": published_scores_count,
            "detail": "published result(s)",
            "url": reverse("parent_results_home"),
            "icon": "ph-chart-bar",
            "ready": published_scores_count > 0,
        },
        {
            "key": "announcements",
            "title": "Announcements",
            "metric": len(announcements),
            "detail": "recent notice(s)",
            "url": reverse("parent_announcements_list"),
            "icon": "ph-megaphone",
            "ready": True,
        },
        {
            "key": "documents",
            "title": "Documents",
            "metric": document_count,
            "detail": "school document(s)",
            "url": reverse("parent_documents_list"),
            "icon": "ph-file-doc",
            "ready": document_count > 0,
        },
        {
            "key": "preferences",
            "title": "Preferences",
            "metric": "On" if preferences_ready else "Off",
            "detail": "message consent and digest settings",
            "url": reverse("parent_communication_preferences"),
            "icon": "ph-bell",
            "ready": preferences_ready,
        },
    ]
    return {
        "today": today,
        "cards": cards,
        "announcements": announcements,
        "documents": documents,
        "ready_count": sum(1 for card in cards if card["ready"]),
        "total": len(cards),
    }


def landing_page(request):
    """
    Landing page with smart redirect based on user authentication and role.
    - If authenticated: redirect to appropriate portal based on user's role
    - If not authenticated: show portal selection page with login prompt
    """
    if request.user.is_authenticated:
        if request.user.has_role(Role.ADMIN) or request.user.has_role(Role.CAMPUS_ADMIN):
            return redirect("admin_home")
        if request.user.has_role(Role.TEACHER):
            return redirect("teacher_home")
        if request.user.has_role(Role.STUDENT):
            return redirect("student_home")
        if request.user.has_role(Role.PARENT):
            return redirect("parent_home")
        return redirect("login")
    
    # Not authenticated - show beautiful landing page
    return render(request, 'landing.html')


@admin_portal_required
def admin_home(request):
    scoped = get_user_campus_scope(request.user)
    students_qs = StudentProfile.objects.all()
    teachers_qs = TeacherProfile.objects.all()
    parents_qs = ParentProfile.objects.all()
    offerings_qs = CourseOffering.objects.all()
    enrollments_qs = Enrollment.objects.all()
    if scoped:
        students_qs = students_qs.filter(campus=scoped)
        teachers_qs = teachers_qs.filter(campus=scoped)
        parents_qs = parents_qs.filter(parentstudentlink__student__campus=scoped).distinct()
        offerings_qs = offerings_qs.filter(campus=scoped)
        enrollments_qs = enrollments_qs.filter(campus=scoped)

    students_total = students_qs.count()
    students_active = students_qs.filter(is_active=True).count()
    teachers_total = teachers_qs.count()
    teachers_active = teachers_qs.filter(is_active=True).count()
    parents_total = parents_qs.count()
    parents_active = parents_qs.filter(is_active=True).count()

    current_year = AcademicYear.objects.filter(is_current=True).order_by("-name").first()
    current_term = AcademicTerm.objects.filter(is_current=True).select_related("year").first()

    offerings_total = offerings_qs.count()
    offerings_active = offerings_qs.filter(is_active=True).count()
    enrollments_total = enrollments_qs.count()
    enrollments_active = enrollments_qs.filter(status=Enrollment.ACTIVE).count()

    campus = get_current_campus(request)
    effective_campus = scoped or campus
    inv_qs = Invoice.objects.all()
    g_qs = Grievance.objects.all()
    if effective_campus:
        inv_qs = inv_qs.filter(student__campus_id=effective_campus.id)
        g_qs = g_qs.filter(Q(campus=effective_campus) | Q(campus__isnull=True))

    invoices_overdue_count = filter_invoices_overdue(inv_qs).count()
    grievances_open_count = g_qs.filter(status=Grievance.OPEN).count()
    grievances_in_progress_count = g_qs.filter(status=Grievance.IN_PROGRESS).count()

    school_setup = school_setup_progress()
    school_health = build_school_health_score()

    return render(
        request,
        "portals/admin/home.html",
        {
            "students_total": students_total,
            "students_active": students_active,
            "teachers_total": teachers_total,
            "teachers_active": teachers_active,
            "parents_total": parents_total,
            "parents_active": parents_active,
            "current_year": current_year,
            "current_term": current_term,
            "offerings_total": offerings_total,
            "offerings_active": offerings_active,
            "enrollments_total": enrollments_total,
            "enrollments_active": enrollments_active,
            "dashboard_campus": campus,
            "invoices_overdue_count": invoices_overdue_count,
            "grievances_open_count": grievances_open_count,
            "grievances_in_progress_count": grievances_in_progress_count,
            "school_setup": school_setup,
            "school_health": school_health,
            "poll_dashboard_items": _poll_items(request),
        },
    )


@role_required(Role.PARENT)
def parent_results_pin_security(request):
    parent_profile = ParentProfile.objects.filter(user=request.user).first()
    if not parent_profile:
        return HttpResponseForbidden("No parent profile linked to this account.")

    if request.method == "POST":
        form = ParentResultsPinSelfServiceForm(request.POST, parent_profile=parent_profile)
        if form.is_valid():
            if form.cleaned_data.get("clear_pin"):
                parent_profile.results_access_pin_hash = ""
                parent_profile.save(update_fields=["results_access_pin_hash"])
                request.session.pop(PARENT_RESULTS_PIN_SESSION_KEY, None)
                messages.success(request, "Your results PIN has been removed.")
            else:
                new_pin = form.cleaned_data["new_pin"]
                parent_profile.results_access_pin_hash = make_password(new_pin)
                parent_profile.save(update_fields=["results_access_pin_hash"])
                request.session.pop(PARENT_RESULTS_PIN_SESSION_KEY, None)
                messages.success(request, "Your results PIN has been updated.")
            return redirect("parent_results_pin_security")
    else:
        form = ParentResultsPinSelfServiceForm(parent_profile=parent_profile)

    return render(
        request,
        "portals/parent/account/results_pin.html",
        {"parent_profile": parent_profile, "form": form},
    )


@role_required(Role.TEACHER)
def teacher_home(request):
    teacher = TeacherProfile.objects.filter(user=request.user).select_related("campus").first()
    offerings_active = 0
    current_year = AcademicYear.objects.filter(is_current=True).order_by("-name").first()
    current_term = AcademicTerm.objects.filter(is_current=True).select_related("year").first()
    if teacher:
        offerings_active = CourseOffering.objects.filter(teacher=teacher, is_active=True).count()
    return render(
        request,
        "portals/teacher/home.html",
        {
            "teacher_profile": teacher,
            "teacher_offerings_active": offerings_active,
            "teacher_current_year": current_year,
            "teacher_current_term": current_term,
            "teacher_daily_workflow": _teacher_daily_workflow(teacher),
            "poll_dashboard_items": _poll_items(request),
        },
    )


@role_required(Role.STUDENT)
def student_home(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    student_invoices_outstanding = 0
    student_invoices_overdue = 0
    if student:
        inv_base = Invoice.objects.filter(student=student)
        student_invoices_outstanding = filter_invoices_outstanding(inv_base).count()
        student_invoices_overdue = filter_invoices_overdue(inv_base).count()
    return render(
        request,
        "portals/student/home.html",
        {
            "student": student,
            "student_invoices_outstanding": student_invoices_outstanding,
            "student_invoices_overdue": student_invoices_overdue,
            "poll_dashboard_items": _poll_items(request),
        },
    )


@role_required(Role.PARENT)
def parent_home(request):
    update_current_campus_from_request(request)

    parent_profile = ParentProfile.objects.filter(user=request.user).first()
    links = []
    if parent_profile:
        qs = (
            ParentStudentLink.objects.filter(parent=parent_profile)
            .select_related("student", "student__campus")
            .order_by("-is_primary", "student__last_name", "student__first_name")
        )

        campus_id = selected_campus_id_from_request(request)
        if campus_id:
            qs = qs.filter(student__campus_id=campus_id)

        links = list(qs)

    campuses = campus_queryset()
    selected_campus_id = selected_campus_id_from_request(request)

    groups = {}
    for link in links:
        key = link.student.campus.name if getattr(link.student, "campus", None) else "Unassigned"
        groups.setdefault(key, []).append(link)

    parent_invoices_outstanding = 0
    parent_invoices_overdue = 0
    if links:
        student_ids = [link.student_id for link in links]
        inv_base = Invoice.objects.filter(student_id__in=student_ids)
        parent_invoices_outstanding = filter_invoices_outstanding(inv_base).count()
        parent_invoices_overdue = filter_invoices_overdue(inv_base).count()

    return render(
        request,
        "portals/parent/home.html",
        {
            "parent_profile": parent_profile,
            "links": links,
            "children_groups": list(groups.items()),
            "campuses": campuses,
            "selected_campus_id": selected_campus_id,
            "parent_invoices_outstanding": parent_invoices_outstanding,
            "parent_invoices_overdue": parent_invoices_overdue,
            "parent_daily_workflow": _parent_daily_workflow(parent_profile, links),
            "poll_dashboard_items": _poll_items(request),
        },
    )


@role_required(Role.PARENT)
def parent_communication_preferences(request):
    from django.utils import timezone

    from apps.tenant.parents.forms import ParentCommunicationPreferencesForm

    parent_profile = ParentProfile.objects.filter(user=request.user).first()
    if not parent_profile:
        return HttpResponseForbidden("No parent profile linked to this account.")

    if request.method == "POST":
        form = ParentCommunicationPreferencesForm(request.POST, instance=parent_profile)
        if form.is_valid():
            obj = form.save(commit=False)
            sms_before = parent_profile.allow_sms_alerts
            wa_before = parent_profile.allow_whatsapp_alerts
            if (
                obj.allow_sms_alerts != sms_before
                or obj.allow_whatsapp_alerts != wa_before
            ):
                obj.communication_consent_updated_at = timezone.now()
            obj.save()
            messages.success(request, "Your message preferences were saved.")
            return redirect("parent_communication_preferences")
    else:
        form = ParentCommunicationPreferencesForm(instance=parent_profile)

    return render(
        request,
        "portals/parent/account/communication_preferences.html",
        {"parent_profile": parent_profile, "form": form},
    )


def pwa_manifest(request):
    """Minimal Web App Manifest for installable mobile web (PWA-lite)."""
    return JsonResponse(
        {
            "name": "EduManage",
            "short_name": "EduManage",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f9fafb",
            "theme_color": "#2563eb",
            "icons": [
                {
                    "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 72 72'%3E%3Crect width='72' height='72' rx='16' fill='%232563eb'/%3E%3Cpath d='M10 27 36 16l26 11-26 11L10 27Z' fill='white'/%3E%3Cpath d='M20 34v12c4 5 11 8 16 8s12-3 16-8V34L36 41 20 34Z' fill='white' opacity='.9'/%3E%3C/svg%3E",
                    "sizes": "72x72",
                    "type": "image/svg+xml",
                    "purpose": "any",
                }
            ],
        }
    )
