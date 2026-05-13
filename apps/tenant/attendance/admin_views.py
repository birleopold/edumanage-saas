from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, render

from apps.tenant.finance import services as finance_services
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from .models import AttendanceEntry, AttendanceSession


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


@admin_portal_required
def session_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page")
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
    ).all()

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

    per_page = 25
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = 25
    per_page = max(1, min(per_page, 200))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/attendance/sessions_list.html",
        {
            "sessions": page_obj.object_list,
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

    entries = AttendanceEntry.objects.filter(session=session).select_related("student")

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

    return render(
        request,
        "portals/admin/attendance/session_detail.html",
        {
            "session": session,
            "entries": entries,
        },
    )
