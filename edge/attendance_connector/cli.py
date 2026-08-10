from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import load_config
from .queue import DurableQueue
from .runner import AttendanceEdgeRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EduManage attendance edge connector")
    parser.add_argument("--config", default="edge-attendance.json", help="Path to connector JSON configuration")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Run continuously")
    sub.add_parser("once", help="Poll sources and deliver one cycle")
    sub.add_parser("status", help="Show local durable queue state")
    sub.add_parser("validate", help="Validate configuration and secret availability")
    purge = sub.add_parser("purge", help="Purge old delivered queue rows")
    purge.add_argument("--days", type=int, default=7)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        try:
            config.device_key()
        except Exception as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {
                    "ok": True,
                    "server_url": config.normalized_server_url,
                    "device_code": config.device_code,
                    "queue_path": config.queue_path,
                    "sources": [source.name for source in config.sources],
                },
                indent=2,
            )
        )
        return 0

    queue = DurableQueue(config.queue_path)
    if args.command == "status":
        print(json.dumps(queue.stats(), indent=2))
        return 0
    if args.command == "purge":
        if args.days < 1:
            print("--days must be at least 1", file=sys.stderr)
            return 2
        deleted = queue.purge_delivered(args.days * 24 * 3600)
        print(json.dumps({"purged": deleted}, indent=2))
        return 0

    runner = AttendanceEdgeRunner(config)
    if args.command == "once":
        print(json.dumps(runner.run_once().__dict__, indent=2))
        return 0
    if args.command == "run":
        try:
            runner.run_forever()
        except KeyboardInterrupt:
            print("Attendance edge connector stopped.")
            return 0
    return 0
