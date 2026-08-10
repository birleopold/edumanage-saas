from __future__ import annotations

import json
from urllib.parse import urlsplit

from django.urls import reverse

from .models import AttendanceDevice


def absolute_endpoint(request, route_name: str) -> str:
    return request.build_absolute_uri(reverse(route_name))


def connection_values(request, device: AttendanceDevice) -> dict:
    event_url = absolute_endpoint(request, "api_attendance_device_events")
    heartbeat_url = absolute_endpoint(request, "api_attendance_device_heartbeat")
    configuration_url = absolute_endpoint(request, "api_attendance_device_configuration")
    parsed = urlsplit(event_url)
    https = parsed.scheme.lower() == "https"
    port = parsed.port or (443 if https else 80)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "base_url": base_url,
        "server_host": parsed.hostname or request.get_host().split(":", 1)[0],
        "server_port": port,
        "scheme": parsed.scheme.lower(),
        "use_https": https,
        "event_url": event_url,
        "event_path": parsed.path,
        "heartbeat_url": heartbeat_url,
        "heartbeat_path": urlsplit(heartbeat_url).path,
        "configuration_url": configuration_url,
        "configuration_path": urlsplit(configuration_url).path,
        "device_code": device.code,
        "timezone": device.timezone_name,
        "identity_namespace": device.identity_namespace,
    }


def _explicit_canonical_push(device: AttendanceDevice) -> bool:
    protocol = (device.protocol or "").strip().lower()
    settings = device.settings or {}
    return bool(
        settings.get("supports_canonical_https_push")
        or protocol in {"canonical-json", "http-json", "https-json", "webhook", "webhook-json"}
    )


def recommended_setup(device: AttendanceDevice) -> dict:
    if device.connection_mode == AttendanceDevice.FILE:
        return {
            "kind": "file",
            "title": "CSV / file import",
            "summary": "This machine does not need a live server connection. Export its attendance log and import it through EduManage.",
        }
    if device.connection_mode == AttendanceDevice.EDGE:
        return {
            "kind": "edge",
            "title": "Local Edge Connector",
            "summary": "Run the EduManage connector on a school PC or Raspberry Pi that can reach the machine on the local network.",
        }
    if device.connection_mode == AttendanceDevice.PULL:
        return {
            "kind": "edge",
            "title": "Vendor API / Edge Connector",
            "summary": "The vendor system is polled locally or through its API, then normalized events are sent to EduManage.",
        }
    if device.vendor == AttendanceDevice.GENERIC or _explicit_canonical_push(device):
        return {
            "kind": "direct",
            "title": "Direct HTTPS connection",
            "summary": "This device/middleware is configured as canonical HTTPS capable and can send authenticated attendance JSON directly to EduManage.",
        }
    if device.vendor in {
        AttendanceDevice.ZKTECO,
        AttendanceDevice.HIKVISION,
        AttendanceDevice.SUPREMA,
        AttendanceDevice.OTHER,
    }:
        return {
            "kind": "edge",
            "title": "Edge Connector recommended",
            "summary": "Do not assume the terminal's server/ADMS/API option speaks EduManage's authenticated JSON protocol. Use the local/vendor adapter unless this exact model or middleware is explicitly configured as canonical HTTPS capable.",
        }
    return {
        "kind": "edge",
        "title": "Edge Connector recommended",
        "summary": "Use the local connector until this machine's network protocol has been verified.",
    }


def vendor_instructions(device: AttendanceDevice, values: dict) -> list[dict]:
    common = [
        {"label": "EduManage school domain", "value": values["server_host"], "copy": True},
        {"label": "HTTPS port", "value": str(values["server_port"]), "copy": True},
        {"label": "Protocol", "value": "HTTPS" if values["use_https"] else "HTTP (local testing only)", "copy": True},
        {"label": "EduManage device code", "value": device.code, "copy": True},
    ]
    direct = recommended_setup(device)["kind"] == "direct"
    if device.vendor == AttendanceDevice.ZKTECO:
        return common + [
            {"label": "EduManage event URL", "value": values["event_url"], "copy": True},
            {"label": "Event path", "value": values["event_path"], "copy": True},
            {
                "label": "Connection guidance",
                "value": (
                    "Direct canonical HTTPS push enabled for this record"
                    if direct
                    else "Use ZKTeco SDK/ADMS/vendor bridge through the Edge Connector unless the exact model supports custom authenticated JSON POST"
                ),
                "copy": False,
            },
        ]
    if device.vendor == AttendanceDevice.HIKVISION:
        return common + [
            {"label": "EduManage event URL", "value": values["event_url"], "copy": True},
            {
                "label": "Connection guidance",
                "value": (
                    "Direct canonical HTTPS push enabled for this record"
                    if direct
                    else "Use a Hikvision event/API bridge or Edge Connector; do not paste this URL into an incompatible ISAPI event field"
                ),
                "copy": False,
            },
        ]
    if device.vendor == AttendanceDevice.SUPREMA:
        return common + [
            {"label": "EduManage event URL", "value": values["event_url"], "copy": True},
            {
                "label": "Connection guidance",
                "value": (
                    "Direct canonical HTTPS push enabled for this record"
                    if direct
                    else "Use a BioStar/G-SDK event bridge or Edge Connector"
                ),
                "copy": False,
            },
        ]
    return common + [
        {"label": "Event endpoint", "value": values["event_url"], "copy": True},
        {"label": "Heartbeat endpoint", "value": values["heartbeat_url"], "copy": True},
        {"label": "Configuration endpoint", "value": values["configuration_url"], "copy": True},
    ]


def edge_config(device: AttendanceDevice, values: dict) -> dict:
    source_settings: dict = {
        "type": "command_json",
        "name": f"{device.vendor.lower()}-{device.code.lower()}",
        "command": ["python", "vendor_bridge.py"],
        "timeout_seconds": 30,
    }
    return {
        "server_url": values["base_url"],
        "device_code": device.code,
        "queue_path": "./data/attendance-edge.sqlite3",
        "device_key_env": "EDUMANAGE_ATTENDANCE_DEVICE_KEY",
        "poll_seconds": 5,
        "batch_size": 100,
        "heartbeat_seconds": 60,
        "request_timeout_seconds": 20,
        "sources": [source_settings],
    }


def edge_config_json(device: AttendanceDevice, values: dict) -> str:
    return json.dumps(edge_config(device, values), indent=2)


def example_event(device: AttendanceDevice) -> dict:
    return {
        "event_id": "923448",
        "person_id": "STU-0042",
        "timestamp": "2026-08-10T07:42:18+03:00",
        "direction": "IN",
        "auth_method": "FACE",
        "event_code": "ACCESS_GRANTED",
    }
