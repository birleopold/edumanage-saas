from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from . import __version__
from .config import ConnectorConfig


class EduManageClientError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


class EduManageAttendanceClient:
    def __init__(self, config: ConnectorConfig):
        self.config = config

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"EduManage-Attendance-Edge/{__version__}",
            "X-Device-Code": self.config.device_code,
            "X-Device-Key": self.config.device_key(),
        }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.config.normalized_server_url}{path}"
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url=url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise EduManageClientError("EduManage response exceeded 5 MB safety limit.")
                if not raw:
                    return {}
                parsed = json.loads(raw.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise EduManageClientError("EduManage returned a non-object JSON response.")
                return parsed
        except urllib.error.HTTPError as exc:
            body = exc.read(8192).decode("utf-8", errors="replace")
            try:
                detail = json.loads(body).get("detail")
            except Exception:
                detail = body.strip()
            raise EduManageClientError(
                f"EduManage HTTP {exc.code}: {detail or exc.reason}", status=exc.code
            ) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise EduManageClientError(f"EduManage is unreachable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise EduManageClientError("EduManage returned invalid JSON.") from exc

    def send_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {"received": 0, "results": []}
        if len(events) > 500:
            raise ValueError("EduManage accepts at most 500 attendance events per batch.")
        return self._request(
            "POST",
            "/api/v1/attendance/devices/events/",
            {"events": events},
        )

    def heartbeat(self, *, queue_stats: dict[str, int], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "device_time": datetime.now(timezone.utc).isoformat(),
            "connector": {
                "name": "edumanage-attendance-edge",
                "version": __version__,
                "hostname": socket.gethostname(),
            },
            "queue": queue_stats,
        }
        if extra:
            payload["edge"] = extra
        return self._request("POST", "/api/v1/attendance/devices/heartbeat/", payload)

    def configuration(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/attendance/devices/configuration/")
