from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    type: str
    name: str
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorConfig:
    server_url: str
    device_code: str
    queue_path: str
    device_key_env: str = "EDUMANAGE_ATTENDANCE_DEVICE_KEY"
    device_key_file: str = ""
    poll_seconds: float = 5.0
    batch_size: int = 100
    heartbeat_seconds: int = 60
    request_timeout_seconds: int = 20
    sources: tuple[SourceConfig, ...] = ()

    @property
    def normalized_server_url(self) -> str:
        return self.server_url.rstrip("/")

    def device_key(self) -> str:
        value = os.environ.get(self.device_key_env, "").strip()
        if value:
            return value
        if self.device_key_file:
            secret_path = Path(self.device_key_file).expanduser()
            if secret_path.exists():
                value = secret_path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        raise RuntimeError(
            f"Attendance device key is missing. Set {self.device_key_env} or configure device_key_file."
        )


def _positive_number(value: Any, name: str, *, minimum: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if number <= minimum:
        raise ValueError(f"{name} must be greater than {minimum}.")
    return number


def load_config(path: str | os.PathLike[str]) -> ConnectorConfig:
    config_path = Path(path).expanduser().resolve()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Edge connector configuration must be a JSON object.")

    server_url = str(raw.get("server_url") or "").strip()
    device_code = str(raw.get("device_code") or "").strip()
    if not server_url.startswith("https://") and not server_url.startswith("http://127.0.0.1") and not server_url.startswith("http://localhost"):
        raise ValueError("server_url must use HTTPS (HTTP is allowed only for localhost testing).")
    if not device_code:
        raise ValueError("device_code is required.")

    queue_value = str(raw.get("queue_path") or "./data/attendance-edge.sqlite3").strip()
    queue_path = Path(queue_value).expanduser()
    if not queue_path.is_absolute():
        queue_path = config_path.parent / queue_path

    key_file_value = str(raw.get("device_key_file") or "").strip()
    if key_file_value:
        key_file = Path(key_file_value).expanduser()
        if not key_file.is_absolute():
            key_file = config_path.parent / key_file
        key_file_value = str(key_file)

    source_configs: list[SourceConfig] = []
    for index, source in enumerate(raw.get("sources") or []):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{index}] must be an object.")
        source_type = str(source.get("type") or "").strip().lower()
        name = str(source.get("name") or f"source-{index + 1}").strip()
        if not source_type:
            raise ValueError(f"Sources[{index}] requires type.")
        source_configs.append(
            SourceConfig(
                type=source_type,
                name=name,
                settings={key: value for key, value in source.items() if key not in {"type", "name"}},
            )
        )

    batch_size = int(_positive_number(raw.get("batch_size", 100), "batch_size"))
    if batch_size > 500:
        raise ValueError("batch_size cannot exceed EduManage's 500-event API limit.")

    return ConnectorConfig(
        server_url=server_url,
        device_code=device_code,
        queue_path=str(queue_path),
        device_key_env=str(raw.get("device_key_env") or "EDUMANAGE_ATTENDANCE_DEVICE_KEY").strip(),
        device_key_file=key_file_value,
        poll_seconds=_positive_number(raw.get("poll_seconds", 5), "poll_seconds"),
        batch_size=batch_size,
        heartbeat_seconds=int(_positive_number(raw.get("heartbeat_seconds", 60), "heartbeat_seconds")),
        request_timeout_seconds=int(_positive_number(raw.get("request_timeout_seconds", 20), "request_timeout_seconds")),
        sources=tuple(source_configs),
    )
