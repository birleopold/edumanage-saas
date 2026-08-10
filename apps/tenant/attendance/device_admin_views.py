import csv
from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .device_forms import (
    AttendanceCSVImportForm,
    AttendanceDeviceForm,
    AttendanceIdentityForm,
    AttendanceManualAdjustmentForm,
    AttendancePolicyForm,
)
from .device_services import (
    apply_manual_adjustment,
    clear_manual_adjustment,
    finalize_absences,
    import_csv_events,
    reprocess_unmatched_identity,
)
from .models import (
    AttendanceDailyRecord,
    AttendanceDevice,
    AttendanceEvent,
    AttendanceIdentity,
    AttendancePolicy,
)


def _campuses_for(user):
    org = get_or_create_organization()
    scoped = get_user_campus_scope(user)
    qs = Campus.objects.filter(organization=org, is_active=True).order_by("name")
    return qs.filter(pk=scoped.pk) if scoped is not None else qs


def _device_qs_for(user):
    qs = AttendanceDevice.objects.select_related("campus")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _policy_qs_for(user):
    qs = AttendancePolicy.objects.select_related("campus")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _daily_qs_for(user):
    qs = AttendanceDailyRecord.objects.select_related("campus", "student", "staff", "policy")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _event_qs_for(user):
    qs = AttendanceEvent.objects.select_related("device", "device__campus", "student", "staff", "identity")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(device__campus=scoped)
    return qs


def _parse_date(raw, default=None):
    try:
        return date.fromisoformat(raw) if raw else default
    except ValueError:
        return default


@admin_portal_required
def device_dashboard(request):
    devices = list(_device_qs_for(request.user).order_by("campus__name", "name"))
    today = timezone.localdate()
    records = _daily_qs_for(request.user).filter(date=today)
    recent_events = _event_qs_for(request.user).order_by("-received_at")[:25]
    return render(
        request,
        "portals/admin/attendance/devices/dashboard.html",
        {
            "devices": devices,
            "device_total": len(devices),
            "device_online": sum(1 for item in devices if item.online),
            "device_offline": sum(1 for item in devices if not item.online),
            "unmatched_events": _event_qs_for(request.user).filter(processing_status=AttendanceEvent.UNMATCHED).count(),
            "today_records": records.count(),
            "today_late": records.filter(status=AttendanceDailyRecord.LATE).count(),
            "today_absent": records.filter(status=AttendanceDailyRecord.ABSENT).count(),
            "today_partial": records.filter(status=AttendanceDailyRecord.PARTIAL).count(),
            "recent_events": recent_events,
            "today": today,
        },
    )


@admin_portal_required
def device_list(request):
    q = (request.GET.get("q") or "").strip()
    vendor = (request.GET.get("vendor") or "").strip()
    qs = _device_qs_for(request.user).order_by("campus__name", "name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(serial_number__icontains=q) | Q(location__icontains=q))
    if vendor:
        qs = qs.filter(vendor=vendor)
    return render(
        request,
        "portals/admin/attendance/devices/device_list.html",
        {"devices": qs, "q": q, "vendor": vendor, "vendor_choices": AttendanceDevice.VENDOR_CHOICES},
    )


@admin_portal_required
def device_create(request):
    scoped = get_user_campus_scope(request.user)
    form = AttendanceDeviceForm(request.POST or None, campus_scope=scoped)
    if request.method == "POST" and form.is_valid():
        device = form.save()
        if not device.identity_namespace or device.identity_namespace == "default":
            device.identity_namespace = f"campus-{device.campus_id}" if device.campus_id else "default"
            device.save(update_fields=["identity_namespace", "updated_at"])
        raw_token = device.rotate_token()
        request.session["attendance_device_token"] = {"device_id": device.id, "token": raw_token}
        messages.success(request, "Attendance device created. Copy its device key now; it will not be shown again.")
        return redirect("admin_attendance_device_detail", pk=device.pk)
    return render(request, "portals/admin/attendance/devices/device_form.html", {"form": form, "title": "Add attendance device"})


@admin_portal_required
def device_edit(request, pk):
    device = get_object_or_404(_device_qs_for(request.user), pk=pk)
    scoped = get_user_campus_scope(request.user)
    form = AttendanceDeviceForm(request.POST or None, instance=device, campus_scope=scoped)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Attendance device settings updated.")
        return redirect("admin_attendance_device_detail", pk=device.pk)
    return render(request, "portals/admin/attendance/devices/device_form.html", {"form": form, "title": f"Edit {device.name}", "device": device})


@admin_portal_required
def device_detail(request, pk):
    device = get_object_or_404(_device_qs_for(request.user), pk=pk)
    token_payload = request.session.pop("attendance_device_token", None)
    raw_token = token_payload.get("token") if token_payload and token_payload.get("device_id") == device.id else ""
    identity_form = AttendanceIdentityForm(request.POST or None, device=device)

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == "rotate_token":
            raw_token = device.rotate_token()
            messages.warning(request, "Device key rotated. Update the machine or edge connector before its next sync.")
        elif action == "add_identity" and identity_form.is_valid():
            try:
                identity = identity_form.save()
            except (IntegrityError, ValueError):
                identity_form.add_error("external_person_id", "This user ID is already mapped in the device namespace.")
            else:
                count = reprocess_unmatched_identity(identity)
                messages.success(request, f"Identity mapping saved. Reprocessed {count} previously unmatched event(s).")
                return redirect("admin_attendance_device_detail", pk=device.pk)
        elif action == "disable_identity":
            identity = get_object_or_404(
                AttendanceIdentity,
                pk=request.POST.get("identity_id"),
                namespace=device.identity_namespace,
            )
            identity.is_active = False
            identity.save(update_fields=["is_active", "updated_at"])
            messages.success(request, "Identity mapping disabled. Historical events were preserved.")
            return redirect("admin_attendance_device_detail", pk=device.pk)

    identities = AttendanceIdentity.objects.filter(namespace=device.identity_namespace).select_related("student", "staff").order_by("external_person_id")[:300]
    events = device.events.select_related("student", "staff", "identity").order_by("-occurred_at")[:100]
    return render(
        request,
        "portals/admin/attendance/devices/device_detail.html",
        {
            "device": device,
            "raw_token": raw_token,
            "identity_form": identity_form,
            "identities": identities,
            "events": events,
            "event_endpoint": "/api/v1/attendance/devices/events/",
            "heartbeat_endpoint": "/api/v1/attendance/devices/heartbeat/",
            "configuration_endpoint": "/api/v1/attendance/devices/configuration/",
        },
    )


@admin_portal_required
def policy_list(request):
    policies = _policy_qs_for(request.user).order_by("person_type", "campus__name", "-is_default", "name")
    return render(request, "portals/admin/attendance/devices/policy_list.html", {"policies": policies})


@admin_portal_required
def policy_create(request):
    scoped = get_user_campus_scope(request.user)
    form = AttendancePolicyForm(request.POST or None, campus_scope=scoped)
    if request.method == "POST" and form.is_valid():
        policy = form.save()
        if policy.is_default:
            AttendancePolicy.objects.filter(
                person_type=policy.person_type,
                campus=policy.campus,
                is_default=True,
            ).exclude(pk=policy.pk).update(is_default=False)
        messages.success(request, "Attendance policy saved.")
        return redirect("admin_attendance_policy_list")
    return render(request, "portals/admin/attendance/devices/policy_form.html", {"form": form, "title": "Add attendance policy"})


@admin_portal_required
def policy_edit(request, pk):
    policy = get_object_or_404(_policy_qs_for(request.user), pk=pk)
    scoped = get_user_campus_scope(request.user)
    form = AttendancePolicyForm(request.POST or None, instance=policy, campus_scope=scoped)
    if request.method == "POST" and form.is_valid():
        policy = form.save()
        if policy.is_default:
            AttendancePolicy.objects.filter(
                person_type=policy.person_type,
                campus=policy.campus,
                is_default=True,
            ).exclude(pk=policy.pk).update(is_default=False)
        messages.success(request, "Attendance policy updated.")
        return redirect("admin_attendance_policy_list")
    return render(request, "portals/admin/attendance/devices/policy_form.html", {"form": form, "title": f"Edit {policy.name}", "policy": policy})


@admin_portal_required
def event_list(request):
    q = (request.GET.get("q") or "").strip()
    state = (request.GET.get("state") or "").strip()
    device_id = request.GET.get("device") or ""
    qs = _event_qs_for(request.user).order_by("-occurred_at", "-id")
    if q:
        qs = qs.filter(
            Q(external_person_id__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(staff__first_name__icontains=q)
            | Q(staff__last_name__icontains=q)
            | Q(staff__staff_id__icontains=q)
        )
    if state:
        qs = qs.filter(processing_status=state)
    if device_id:
        qs = qs.filter(device_id=device_id)
    page_obj = Paginator(qs, 100).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/attendance/devices/event_list.html",
        {
            "page_obj": page_obj,
            "events": page_obj.object_list,
            "q": q,
            "state": state,
            "device_id": str(device_id),
            "devices": _device_qs_for(request.user).order_by("name"),
            "state_choices": AttendanceEvent.PROCESS_CHOICES,
        },
    )


@admin_portal_required
def daily_list(request):
    selected_date = _parse_date(request.GET.get("date"), timezone.localdate())
    person_type = (request.GET.get("person_type") or AttendanceIdentity.STUDENT).upper()
    status_filter = (request.GET.get("status") or "").upper()
    q = (request.GET.get("q") or "").strip()
    scoped = get_user_campus_scope(request.user)
    campus_id = scoped.id if scoped else request.GET.get("campus") or ""

    if request.method == "POST" and request.POST.get("action") == "finalize_absences":
        day = _parse_date(request.POST.get("date"), timezone.localdate())
        kind = (request.POST.get("person_type") or AttendanceIdentity.STUDENT).upper()
        campus = scoped or get_object_or_404(_campuses_for(request.user), pk=request.POST.get("campus"))
        result = finalize_absences(day=day, campus=campus, person_type=kind)
        if result["skipped"]:
            messages.warning(request, result["reason"])
        else:
            messages.success(request, f"Absence finalization completed. Created {result['created']} absent record(s).")
        target = f"{reverse('admin_attendance_daily_list')}?date={day.isoformat()}&person_type={kind}&campus={campus.id}"
        return redirect(target)

    qs = _daily_qs_for(request.user).filter(date=selected_date, person_type=person_type)
    if campus_id:
        qs = qs.filter(campus_id=campus_id)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(staff__first_name__icontains=q)
            | Q(staff__last_name__icontains=q)
            | Q(staff__staff_id__icontains=q)
        )
    page_obj = Paginator(qs.order_by("student__last_name", "staff__last_name", "id"), 100).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/attendance/devices/daily_list.html",
        {
            "records": page_obj.object_list,
            "page_obj": page_obj,
            "selected_date": selected_date,
            "person_type": person_type,
            "status_filter": status_filter,
            "q": q,
            "campus_id": str(campus_id),
            "campuses": _campuses_for(request.user),
            "person_choices": AttendanceIdentity.PERSON_CHOICES,
            "status_choices": AttendanceDailyRecord.STATUS_CHOICES,
        },
    )


@admin_portal_required
def daily_adjust(request, pk):
    record = get_object_or_404(_daily_qs_for(request.user), pk=pk)
    form = AttendanceManualAdjustmentForm(request.POST or None, record=record)
    if request.method == "POST":
        if request.POST.get("action") == "clear_override":
            reason = request.POST.get("reason") or ""
            try:
                clear_manual_adjustment(record=record, reason=reason, user=request.user)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Manual override cleared and device events reconciled again.")
                return redirect("admin_attendance_daily_list")
        elif form.is_valid():
            apply_manual_adjustment(
                record=record,
                status=form.cleaned_data["status"],
                first_in=form.cleaned_data["first_in"],
                last_out=form.cleaned_data["last_out"],
                note=form.cleaned_data["note"],
                reason=form.cleaned_data["reason"],
                user=request.user,
            )
            messages.success(request, "Attendance correction saved with an audit trail.")
            return redirect("admin_attendance_daily_list")
    return render(request, "portals/admin/attendance/devices/daily_adjust.html", {"record": record, "form": form})


@admin_portal_required
def csv_import(request):
    scoped = get_user_campus_scope(request.user)
    form = AttendanceCSVImportForm(request.POST or None, request.FILES or None, user_campus=scoped)
    summary = None
    if request.method == "POST" and form.is_valid():
        summary = import_csv_events(
            device=form.cleaned_data["device"],
            upload=form.cleaned_data["file"],
            allow_system_id_fallback=form.cleaned_data["auto_match_system_ids"],
        )
        messages.success(
            request,
            "Import complete: {processed} processed, {duplicates} duplicates, {unmatched} unmatched, {errors} errors.".format(**summary),
        )
    return render(request, "portals/admin/attendance/devices/csv_import.html", {"form": form, "summary": summary})


@admin_portal_required
def timesheet_csv(request):
    start = _parse_date(request.GET.get("start"), timezone.localdate().replace(day=1))
    end = _parse_date(request.GET.get("end"), timezone.localdate())
    qs = _daily_qs_for(request.user).filter(
        person_type=AttendanceIdentity.STAFF,
        date__gte=start,
        date__lte=end,
    ).order_by("date", "staff__last_name", "staff__first_name")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="staff-timesheet-{start}-{end}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Staff ID", "Staff name", "Campus", "Status", "First in", "Last out", "Minutes present", "Minutes late", "Early departure minutes", "Manual override"])
    for record in qs.iterator():
        writer.writerow([
            record.date.isoformat(),
            record.staff.staff_id if record.staff_id else "",
            record.staff.get_full_name() if record.staff_id else "",
            record.campus.name if record.campus_id else "",
            record.status,
            record.first_in.isoformat() if record.first_in else "",
            record.last_out.isoformat() if record.last_out else "",
            record.minutes_present,
            record.minutes_late,
            record.minutes_early_departure,
            "YES" if record.manual_override else "NO",
        ])
    return response


@admin_portal_required
def integration_guide(request):
    return render(request, "portals/admin/attendance/devices/integration_guide.html")
