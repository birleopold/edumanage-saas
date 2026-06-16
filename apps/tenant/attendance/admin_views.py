from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, render

from apps.tenant.finance import services as finance_services
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required

from .models import AttendanceEntry, AttendanceSession
from .services import ensure_entries_for_session, session_summary


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
    raw = request.GET.get("per_page")
    try:
        value = int(raw) if raw else default
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, max_value))


@admin_portal_required
def session_list(request):
    q = (request.GET.get("q") or "").strip()
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)

    qs = AttendanceSession.objects.select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "taken_by",
    ).prefetch_related("entries").all()

    if campus_id:
        qs = qs.filter(offering__campus_id=campus_id)

    if q:
        qs = qs.filter(
            Q(offering__course__name__icontains=q)
            | Q(offering__course__code__icontains=q)
            | Q(offering__term__name__icontains=q)
            | Q(offering__term__year__name__icontains=q)
            | Q(offering__class_group__name__icontains=q)
            | Q(taken_by__first_name__icontains=q)
            | Q(taken_by__last_name__icontains=q)
        )

    per_page = _parse_per_page(request)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    sessions = list(page_obj.object_list)
    for session in sessions:
        session.summary = session_summary(session)

    return render(
        request,
        "portals/admin/attendance/sessions_list.html",
        {
            "sessions": sessions,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def session_detail(request, pk: int):
    session = get_object_or_404(
        AttendanceSession.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
            "offering__class_group",
            "taken_by",
        ),
        pk=pk,
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "send_absence_alerts":
            include_late = request.POST.get("include_late") == "1"
            dry_run = request.POST.get("dry_run") == "1"
            org = get_or_create_organization()
            summary = finance_services.send_absence_alerts_for_session(
                session,
                include_late=include_late,
                school_name=org.name,
                dry_run=dry_run,
            )
            messages.success(
                request,
                "Absence alerts: sent={sent}, failed={failed}, no_phone={no_phone}, dry_run={dry}".format(
                    sent=summary["sent"],
                    failed=summary["failed"],
                    no_phone=summary["no_phone"],
                    dry=summary["dry_run_count"],
                ),
            )
        elif action == "sync_students":
            created = ensure_entries_for_session(session)
            messages.success(request, f"Attendance list synced. Created {created} missing entry row(s).")

    entries = AttendanceEntry.objects.filter(session=session).select_related("student")
    return render(
        request,
        "portals/admin/attendance/session_detail.html",
        {
            "session": session,
            "entries": entries,
            "summary": session_summary(session),
        },
    )
