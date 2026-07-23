from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.tenant.finance import services as finance_services
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .models import AttendanceEntry, AttendanceSession
from .services import ensure_entries_for_session, session_summary


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _campus_queryset_for(user):
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        return Campus.objects.filter(pk=scoped.pk)
    return _campus_queryset()


def _session_queryset_for(user):
    qs = AttendanceSession.objects.select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "taken_by",
    ).prefetch_related("entries")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(offering__campus=scoped)
    return qs


def _selected_campus_id(request):
    scoped = get_user_campus_scope(request.user)
    current = scoped or get_current_campus(request)
    if scoped is not None:
        return scoped.id
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


def _attendance_overview(queryset):
    totals = queryset.aggregate(
        total_entries=Count("entries"),
        present=Count("entries", filter=Q(entries__status=AttendanceEntry.PRESENT)),
        absent=Count("entries", filter=Q(entries__status=AttendanceEntry.ABSENT)),
        late=Count("entries", filter=Q(entries__status=AttendanceEntry.LATE)),
        excused=Count("entries", filter=Q(entries__status=AttendanceEntry.EXCUSED)),
    )
    total_entries = totals["total_entries"] or 0
    present = totals["present"] or 0
    totals.update(
        {
            "sessions": queryset.count(),
            "today_sessions": queryset.filter(date=timezone.localdate()).count(),
            "present_rate": round((present / total_entries) * 100) if total_entries else 0,
        }
    )
    return totals


@admin_portal_required
def session_list(request):
    q = (request.GET.get("q") or "").strip()
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset_for(request.user)
    campus_id = _selected_campus_id(request)

    qs = _session_queryset_for(request.user)

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

    overview = _attendance_overview(qs)
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
            "attendance_overview": overview,
        },
    )


@admin_portal_required
def session_detail(request, pk: int):
    session = get_object_or_404(
        _session_queryset_for(request.user),
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
