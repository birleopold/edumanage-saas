import json
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from edge.attendance_connector.client import EduManageAttendanceClient
from edge.attendance_connector.config import ConnectorConfig, SourceConfig, load_config
from edge.attendance_connector.queue import DurableQueue, QueuedEvent
from edge.attendance_connector.runner import AttendanceEdgeRunner
from edge.attendance_connector.sources import CommandJsonSource, DropDirectorySource


class AttendanceEdgeConnectorTests(SimpleTestCase):
    def test_config_requires_https_except_localhost(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "edge.json"
            path.write_text(
                json.dumps({"server_url": "http://school.example.test", "device_code": "GATE-1"}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(path)

            path.write_text(
                json.dumps({"server_url": "http://127.0.0.1:8000", "device_code": "GATE-1"}),
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.normalized_server_url, "http://127.0.0.1:8000")

    def test_device_secret_is_read_from_environment_not_config_queue(self):
        config = ConnectorConfig(
            server_url="https://school.example.test",
            device_code="GATE-1",
            queue_path="/tmp/unused.sqlite3",
        )
        with mock.patch.dict(os.environ, {"EDUMANAGE_ATTENDANCE_DEVICE_KEY": "secret-value"}, clear=False):
            self.assertEqual(config.device_key(), "secret-value")

    def test_sqlite_queue_is_durable_and_deduplicates_same_event(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "queue.sqlite3")
            queue = DurableQueue(path)
            event = {"event_id": "1001", "person_id": "42", "timestamp": "2026-08-10T07:30:00+03:00"}
            self.assertTrue(queue.enqueue(event))
            self.assertFalse(queue.enqueue(event))
            self.assertEqual(queue.stats()["pending"], 1)

            reopened = DurableQueue(path)
            pending = reopened.pending(10)
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].payload["event_id"], "1001")

    def test_edge_queue_scrubs_biometric_images_and_templates_before_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = DurableQueue(str(Path(folder) / "queue.sqlite3"))
            queue.enqueue(
                {
                    "event_id": "bio-1",
                    "person_id": "42",
                    "face_image": "base64-photo-material",
                    "nested": {"fingerprint_template": "template-bytes", "event_code": "ACCESS_GRANTED"},
                }
            )
            payload = queue.pending(10)[0].payload
            self.assertEqual(payload["event_id"], "bio-1")
            self.assertEqual(payload["face_image"], "[REDACTED_BY_EDUMANAGE_EDGE]")
            self.assertEqual(payload["nested"]["fingerprint_template"], "[REDACTED_BY_EDUMANAGE_EDGE]")
            self.assertEqual(payload["nested"]["event_code"], "ACCESS_GRANTED")

    def test_failed_delivery_is_retained_for_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = DurableQueue(str(Path(folder) / "queue.sqlite3"))
            queue.enqueue({"event_id": "1001", "person_id": "42"})
            pending = queue.pending(10)
            queue.mark_retry([pending[0].id], "internet unavailable")
            stats = queue.stats()
            self.assertEqual(stats["pending"], 1)
            self.assertEqual(stats["retrying"], 1)

    def test_delivered_event_can_be_purged_without_touching_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = DurableQueue(str(Path(folder) / "queue.sqlite3"))
            queue.enqueue({"event_id": "a"})
            queue.enqueue({"event_id": "b"})
            pending = queue.pending(10)
            queue.mark_delivered([pending[0].id])
            self.assertEqual(queue.stats(), {"pending": 1, "delivered": 1, "retrying": 0})
            queue.purge_delivered(older_than_seconds=-1)
            self.assertEqual(queue.stats(), {"pending": 1, "delivered": 0, "retrying": 0})

    def test_runner_only_marks_server_persisted_results_as_delivered(self):
        batch = [
            QueuedEvent(id=1, payload={"event_id": "a"}, attempts=0),
            QueuedEvent(id=2, payload={"event_id": "b"}, attempts=0),
        ]
        delivered, retry, error = AttendanceEdgeRunner._partition_delivery(
            batch,
            {
                "results": [
                    {"id": 91, "status": "PROCESSED", "created": True},
                    {"id": None, "status": "ERROR", "error": "temporary failure"},
                ]
            },
        )
        self.assertEqual(delivered, [1])
        self.assertEqual(retry, [2])
        self.assertIn("temporary failure", error)

    def test_command_source_receives_cursor_and_reads_canonical_events(self):
        source = CommandJsonSource(
            SourceConfig(type="command_json", name="vendor", settings={"command": ["bridge"]})
        )
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps({"events": [{"event_id": "a", "person_id": "1"}], "next_cursor": "a"}),
            stderr="",
        )
        with mock.patch("edge.attendance_connector.sources.subprocess.run", return_value=completed) as run:
            batch = source.poll("previous")
        self.assertEqual(batch.next_cursor, "a")
        self.assertEqual(batch.events[0]["event_id"], "a")
        self.assertEqual(run.call_args.kwargs["env"]["EDUMANAGE_EDGE_CURSOR"], "previous")

    def test_drop_directory_archives_after_events_are_read(self):
        with tempfile.TemporaryDirectory() as folder:
            inbox = Path(folder) / "inbox"
            archive = Path(folder) / "archive"
            inbox.mkdir()
            (inbox / "events.json").write_text(
                json.dumps([{"event_id": "a", "person_id": "1"}]), encoding="utf-8"
            )
            source = DropDirectorySource(
                SourceConfig(
                    type="drop_directory",
                    name="drop",
                    settings={"path": str(inbox), "archive_path": str(archive)},
                )
            )
            batch = source.poll("")
            self.assertEqual(len(batch.events), 1)
            source.acknowledge(batch)
            self.assertFalse((inbox / "events.json").exists())
            self.assertEqual(len(list(archive.glob("*events.json"))), 1)

    def test_client_sends_device_headers_without_putting_secret_in_url(self):
        config = ConnectorConfig(
            server_url="https://school.example.test",
            device_code="GATE-1",
            queue_path="/tmp/unused.sqlite3",
        )
        client = EduManageAttendanceClient(config)
        with mock.patch.dict(os.environ, {"EDUMANAGE_ATTENDANCE_DEVICE_KEY": "secret-value"}, clear=False):
            headers = client._headers()
        self.assertEqual(headers["X-Device-Code"], "GATE-1")
        self.assertEqual(headers["X-Device-Key"], "secret-value")
        self.assertNotIn("secret-value", config.server_url)
