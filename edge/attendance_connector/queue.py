from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .privacy import scrub_edge_payload


@dataclass(frozen=True)
class QueuedEvent:
    id: int
    payload: dict[str, Any]
    attempts: int


class DurableQueue:
    """Small SQLite-backed store-and-forward queue.

    Payload fingerprints make source retries safe. Events are removed only after the
    EduManage API accepts the batch; transient failures retain the original payload.
    Biometric image/template material is scrubbed before the payload is fingerprinted
    or written to SQLite.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS event_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at REAL NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    delivered_at REAL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS edge_queue_pending_idx
                ON event_queue(delivered_at, next_attempt_at, id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    @staticmethod
    def fingerprint(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def enqueue(self, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            raise ValueError("Queued attendance event must be an object.")
        cleaned = scrub_edge_payload(payload)
        if not isinstance(cleaned, dict):
            raise ValueError("Queued attendance event must remain an object after privacy filtering.")
        encoded = json.dumps(cleaned, separators=(",", ":"), ensure_ascii=False)
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO event_queue(fingerprint, payload_json, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (self.fingerprint(cleaned), encoded, time.time()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def enqueue_many(self, payloads: Iterable[dict[str, Any]]) -> tuple[int, int]:
        created = duplicate = 0
        for payload in payloads:
            if self.enqueue(payload):
                created += 1
            else:
                duplicate += 1
        return created, duplicate

    def pending(self, limit: int) -> list[QueuedEvent]:
        now = time.time()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, payload_json, attempts
                FROM event_queue
                WHERE delivered_at IS NULL AND next_attempt_at <= ?
                ORDER BY id
                LIMIT ?
                """,
                (now, int(limit)),
            ).fetchall()
        return [
            QueuedEvent(
                id=int(row["id"]),
                payload=json.loads(row["payload_json"]),
                attempts=int(row["attempts"]),
            )
            for row in rows
        ]

    def mark_delivered(self, event_ids: Iterable[int]) -> None:
        ids = [int(value) for value in event_ids]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE event_queue SET delivered_at=?, last_error='' WHERE id IN ({placeholders})",
                [time.time(), *ids],
            )

    def mark_retry(self, event_ids: Iterable[int], error: str, *, max_delay: int = 300) -> None:
        ids = [int(value) for value in event_ids]
        if not ids:
            return
        with self.connect() as connection:
            for event_id in ids:
                row = connection.execute("SELECT attempts FROM event_queue WHERE id=?", (event_id,)).fetchone()
                attempts = (int(row["attempts"]) if row else 0) + 1
                delay = min(max_delay, max(2, 2 ** min(attempts, 8)))
                connection.execute(
                    """
                    UPDATE event_queue
                    SET attempts=?, next_attempt_at=?, last_error=?
                    WHERE id=?
                    """,
                    (attempts, time.time() + delay, str(error)[:1000], event_id),
                )

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            pending = connection.execute(
                "SELECT COUNT(*) FROM event_queue WHERE delivered_at IS NULL"
            ).fetchone()[0]
            delivered = connection.execute(
                "SELECT COUNT(*) FROM event_queue WHERE delivered_at IS NOT NULL"
            ).fetchone()[0]
            retrying = connection.execute(
                "SELECT COUNT(*) FROM event_queue WHERE delivered_at IS NULL AND attempts > 0"
            ).fetchone()[0]
        return {"pending": int(pending), "delivered": int(delivered), "retrying": int(retrying)}

    def get_state(self, key: str, default: str = "") -> str:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM connector_state WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_state(self, key: str, value: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO connector_state(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, str(value), time.time()),
            )

    def purge_delivered(self, older_than_seconds: int = 7 * 24 * 3600) -> int:
        cutoff = time.time() - int(older_than_seconds)
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM event_queue WHERE delivered_at IS NOT NULL AND delivered_at < ?",
                (cutoff,),
            )
            return int(cursor.rowcount)
