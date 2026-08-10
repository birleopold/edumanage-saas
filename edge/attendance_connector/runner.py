from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from .client import EduManageAttendanceClient, EduManageClientError
from .config import ConnectorConfig
from .queue import DurableQueue, QueuedEvent
from .sources import EventSource, SourceBatch, build_source


LOGGER = logging.getLogger("edumanage.attendance.edge")


@dataclass
class RunSummary:
    polled_events: int = 0
    queued_events: int = 0
    duplicate_events: int = 0
    delivered_events: int = 0
    retry_events: int = 0
    source_errors: int = 0
    delivery_errors: int = 0


class AttendanceEdgeRunner:
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.queue = DurableQueue(config.queue_path)
        self.client = EduManageAttendanceClient(config)
        self.sources: list[EventSource] = [build_source(item) for item in config.sources]
        self._last_heartbeat = 0.0
        self._last_config_sync = 0.0

    def poll_sources(self, summary: RunSummary) -> None:
        for source in self.sources:
            cursor = self.queue.get_state(source.state_key, "")
            try:
                batch: SourceBatch = source.poll(cursor)
                summary.polled_events += len(batch.events)
                created, duplicate = self.queue.enqueue_many(batch.events)
                summary.queued_events += created
                summary.duplicate_events += duplicate
                # It is safe to advance the source after events are durably present in SQLite.
                if batch.next_cursor is not None:
                    self.queue.set_state(source.state_key, batch.next_cursor)
                source.acknowledge(batch)
            except Exception as exc:
                summary.source_errors += 1
                LOGGER.exception("Attendance source %s failed: %s", source.config.name, exc)

    @staticmethod
    def _partition_delivery(batch: list[QueuedEvent], response: dict) -> tuple[list[int], list[int], str]:
        results = response.get("results")
        if not isinstance(results, list) or len(results) != len(batch):
            return [], [item.id for item in batch], "EduManage returned an incomplete batch result."

        delivered: list[int] = []
        retry: list[int] = []
        errors: list[str] = []
        for queued, result in zip(batch, results):
            if not isinstance(result, dict):
                retry.append(queued.id)
                errors.append("non-object result")
                continue
            # A persisted event has an id. Exact replay may return created=false but still has the stored event id.
            if result.get("id") is not None:
                delivered.append(queued.id)
            else:
                retry.append(queued.id)
                if result.get("error"):
                    errors.append(str(result.get("error")))
        return delivered, retry, "; ".join(errors)[:1000]

    def deliver_queue(self, summary: RunSummary) -> None:
        batch = self.queue.pending(self.config.batch_size)
        if not batch:
            return
        try:
            response = self.client.send_events([item.payload for item in batch])
        except EduManageClientError as exc:
            summary.delivery_errors += 1
            summary.retry_events += len(batch)
            self.queue.mark_retry([item.id for item in batch], str(exc))
            LOGGER.warning("Attendance delivery failed: %s", exc)
            return

        delivered, retry, error = self._partition_delivery(batch, response)
        if delivered:
            self.queue.mark_delivered(delivered)
            summary.delivered_events += len(delivered)
        if retry:
            self.queue.mark_retry(retry, error or "EduManage did not persist the event.")
            summary.retry_events += len(retry)
            summary.delivery_errors += 1

    def heartbeat_if_due(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_heartbeat < self.config.heartbeat_seconds:
            return
        # Throttle failed heartbeats too; an internet outage must not cause a request storm.
        self._last_heartbeat = now
        try:
            self.client.heartbeat(
                queue_stats=self.queue.stats(),
                extra={"source_count": len(self.sources)},
            )
        except EduManageClientError as exc:
            LOGGER.warning("Attendance heartbeat failed: %s", exc)

    def sync_configuration_if_due(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_config_sync < 300:
            return
        self._last_config_sync = now
        try:
            configuration = self.client.configuration()
            self.queue.set_state(
                "server:configuration",
                json.dumps(configuration, sort_keys=True, separators=(",", ":")),
            )
        except EduManageClientError as exc:
            LOGGER.warning("Attendance configuration sync failed: %s", exc)

    def run_once(self) -> RunSummary:
        summary = RunSummary()
        self.poll_sources(summary)
        self.deliver_queue(summary)
        self.heartbeat_if_due()
        self.sync_configuration_if_due()
        return summary

    def run_forever(self) -> None:
        LOGGER.info(
            "Starting EduManage attendance edge connector for %s with %d source(s)",
            self.config.device_code,
            len(self.sources),
        )
        self.heartbeat_if_due(force=True)
        self.sync_configuration_if_due(force=True)
        while True:
            started = time.monotonic()
            self.run_once()
            elapsed = time.monotonic() - started
            time.sleep(max(0.2, self.config.poll_seconds - elapsed))
