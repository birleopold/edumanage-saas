from __future__ import annotations

import json

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .device_setup import (
    connection_values,
    edge_config_json,
    example_event,
    recommended_setup,
    vendor_instructions,
)
from .models import AttendanceDevice


def _devices_for(user):
    queryset = AttendanceDevice.objects.select_related("campus")
    campus = get_user_campus_scope(user)
    if campus is not None:
        queryset = queryset.filter(campus=campus)
    return queryset


def _connection_state(device: AttendanceDevice) -> dict:
    if device.online and device.last_event_at:
        return {
            "code": "receiving",
            "title": "Connected and receiving attendance",
            "tone": "success",
            "detail": f"Last attendance event received {timezone.localtime(device.last_event_at):%d %b %Y %H:%M:%S}.",
        }
    if device.online:
        return {
            "code": "online",
            "title": "Connected — waiting for attendance events",
            "tone": "blue",
            "detail": "EduManage has recently heard from this device/connector, but no attendance event has been recorded yet.",
        }
    if device.last_seen_at:
        return {
            "code": "offline",
            "title": "Previously connected — currently offline",
            "tone": "warning",
            "detail": f"Last heartbeat/configuration contact was {timezone.localtime(device.last_seen_at):%d %b %Y %H:%M:%S}.",
        }
    return {
        "code": "waiting",
        "title": "Waiting for first connection",
        "tone": "warning",
        "detail": "Enter the generated values into the attendance terminal/vendor software or install the Edge Connector.",
    }


@admin_portal_required
def device_setup(request, pk):
    device = get_object_or_404(_devices_for(request.user), pk=pk)
    raw_token = ""

    token_payload = request.session.pop("attendance_device_token", None)
    if token_payload and token_payload.get("device_id") == device.id:
        raw_token = str(token_payload.get("token") or "")

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == "rotate_token":
            raw_token = device.rotate_token()
            messages.warning(
                request,
                "A new device key was generated. Copy it now and replace the old key in the machine or Edge Connector.",
            )
        elif action == "set_mode":
            mode = (request.POST.get("connection_mode") or "").upper()
            allowed = dict(AttendanceDevice.CONNECTION_CHOICES)
            if mode not in allowed:
                messages.error(request, "Unsupported connection method.")
            else:
                device.connection_mode = mode
                device.save(update_fields=["connection_mode", "updated_at"])
                messages.success(request, f"Connection method changed to {allowed[mode]}.")
                return redirect("admin_attendance_device_setup", pk=device.pk)

    values = connection_values(request, device)
    setup = recommended_setup(device)
    instructions = vendor_instructions(device, values)
    config_json = edge_config_json(device, values)
    sample_event = json.dumps(example_event(device), indent=2)

    curl_example = (
        f"curl -X POST '{values['event_url']}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -H 'X-Device-Code: {device.code}' \\\n"
        "  -H 'X-Device-Key: YOUR_DEVICE_KEY' \\\n"
        f"  --data '{json.dumps(example_event(device), separators=(',', ':'))}'"
    )

    return render(
        request,
        "portals/admin/attendance/devices/setup.html",
        {
            "device": device,
            "raw_token": raw_token,
            "values": values,
            "setup": setup,
            "instructions": instructions,
            "connection_state": _connection_state(device),
            "edge_config_json": config_json,
            "sample_event": sample_event,
            "curl_example": curl_example,
            "connection_choices": AttendanceDevice.CONNECTION_CHOICES,
        },
    )


@admin_portal_required
def device_setup_status(request, pk):
    device = get_object_or_404(_devices_for(request.user), pk=pk)
    state = _connection_state(device)
    return JsonResponse(
        {
            **state,
            "online": device.online,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            "last_event_at": device.last_event_at.isoformat() if device.last_event_at else None,
            "clock_offset_seconds": device.clock_offset_seconds,
            "last_error": device.last_error[:500],
        }
    )


@admin_portal_required
def download_edge_config(request, pk):
    device = get_object_or_404(_devices_for(request.user), pk=pk)
    values = connection_values(request, device)
    response = HttpResponse(edge_config_json(device, values), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="edumanage-attendance-{device.code}.json"'
    response["Cache-Control"] = "no-store"
    return response
