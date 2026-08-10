from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import SourceConfig


@dataclass
class SourceBatch:
    events: list[dict[str, Any]] = field(default_factory=list)
    next_cursor: str | None = None
    acknowledgements: list[str] = field(default_factory=list)


class EventSource:
    def __init__(self, config: SourceConfig):
        self.config = config

    @property
    def state_key(self) -> str:
        return f"source:{self.config.name}:cursor"

    def poll(self, cursor: str) -> SourceBatch:
        raise NotImplementedError

    def acknowledge(self, batch: SourceBatch) -> None:
        return None


class CommandJsonSource(EventSource):
    """Run a vendor bridge command and consume canonical JSON events.

    The command receives the last successful cursor in EDUMANAGE_EDGE_CURSOR and must
    write either a JSON array or {"events": [...], "next_cursor": "..."} to stdout.
    This is the universal escape hatch for proprietary vendor SDKs.
    """

    def poll(self, cursor: str) -> SourceBatch:
        command = self.config.settings.get("command")
        if isinstance(command, str):
            command = shlex.split(command)
        if not isinstance(command, list) or not command:
            raise ValueError(f"Source {self.config.name} requires a command list or string.")
        timeout = int(self.config.settings.get("timeout_seconds") or 30)
        env = dict(os.environ)
        env["EDUMANAGE_EDGE_CURSOR"] = cursor or ""
        process = subprocess.run(
            [str(part) for part in command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        if process.returncode != 0:
            error = process.stderr.strip() or process.stdout.strip() or f"exit {process.returncode}"
            raise RuntimeError(f"Source {self.config.name} failed: {error[:1000]}")
        raw = process.stdout.strip()
        if not raw:
            return SourceBatch()
        data = json.loads(raw)
        if isinstance(data, list):
            events = data
            next_cursor = None
        elif isinstance(data, dict):
            events = data.get("events") or []
            next_cursor = data.get("next_cursor")
        else:
            raise ValueError(f"Source {self.config.name} returned unsupported JSON.")
        if not isinstance(events, list) or any(not isinstance(item, dict) for item in events):
            raise ValueError(f"Source {self.config.name} events must be a list of objects.")
        return SourceBatch(events=list(events), next_cursor=None if next_cursor is None else str(next_cursor))


class DropDirectorySource(EventSource):
    """Consume .json/.jsonl files dropped by vendor export scripts or middleware."""

    def _paths(self) -> tuple[Path, Path]:
        inbox = Path(str(self.config.settings.get("path") or "./attendance-inbox")).expanduser()
        archive = Path(str(self.config.settings.get("archive_path") or (inbox / "archive"))).expanduser()
        inbox.mkdir(parents=True, exist_ok=True)
        archive.mkdir(parents=True, exist_ok=True)
        return inbox, archive

    @staticmethod
    def _read_file(path: Path) -> list[dict[str, Any]]:
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() == ".jsonl":
            events = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("events"), list):
                events = data["events"]
            elif isinstance(data, list):
                events = data
            elif isinstance(data, dict):
                events = [data]
            else:
                raise ValueError(f"Unsupported JSON payload in {path.name}.")
        if any(not isinstance(item, dict) for item in events):
            raise ValueError(f"Every event in {path.name} must be an object.")
        return list(events)

    def poll(self, cursor: str) -> SourceBatch:
        inbox, _ = self._paths()
        events: list[dict[str, Any]] = []
        acknowledgements: list[str] = []
        max_files = int(self.config.settings.get("max_files_per_poll") or 20)
        for path in sorted([*inbox.glob("*.json"), *inbox.glob("*.jsonl")])[:max_files]:
            events.extend(self._read_file(path))
            acknowledgements.append(str(path))
        return SourceBatch(events=events, acknowledgements=acknowledgements)

    def acknowledge(self, batch: SourceBatch) -> None:
        _, archive = self._paths()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for raw_path in batch.acknowledgements:
            path = Path(raw_path)
            if not path.exists():
                continue
            destination = archive / f"{stamp}-{path.name}"
            counter = 1
            while destination.exists():
                destination = archive / f"{stamp}-{counter}-{path.name}"
                counter += 1
            shutil.move(str(path), str(destination))


def build_source(config: SourceConfig) -> EventSource:
    if config.type == "command_json":
        return CommandJsonSource(config)
    if config.type == "drop_directory":
        return DropDirectorySource(config)
    raise ValueError(
        f"Unsupported attendance edge source type {config.type!r}. "
        "Use command_json or drop_directory, or add a vendor-specific source adapter."
    )
