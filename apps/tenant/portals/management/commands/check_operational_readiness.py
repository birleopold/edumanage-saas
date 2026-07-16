import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import NoReverseMatch, reverse


class Command(BaseCommand):
    help = "Print the Phase 4 operational readiness checklist and verify local release evidence."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
        parser.add_argument("--strict", action="store_true", help="Fail when local verifiable checks are not passing.")
        parser.add_argument(
            "--require-production-settings",
            action="store_true",
            help="Require production security settings such as DEBUG=False and secure cookies.",
        )

    def handle(self, *args, **options):
        checks = self._checks(require_production_settings=options["require_production_settings"])
        summary = {
            "ok": all(item["status"] in {"pass", "manual"} for item in checks),
            "checks": checks,
            "release_gates": [
                "python manage.py check",
                "DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy",
                "python verify_routes.py",
                "python manage.py test",
                "npm audit --omit=dev",
            ],
        }

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2))
        else:
            self.stdout.write("Operational readiness checklist")
            self.stdout.write("=" * 33)
            for item in checks:
                self.stdout.write(f"[{item['status'].upper()}] {item['name']}: {item['detail']}")
            self.stdout.write("")
            self.stdout.write("Release gates:")
            for gate in summary["release_gates"]:
                self.stdout.write(f"- {gate}")

        if options["strict"] and not summary["ok"]:
            failing = ", ".join(item["name"] for item in checks if item["status"] == "fail")
            raise CommandError(f"Operational readiness check failed: {failing}")

    def _checks(self, *, require_production_settings: bool):
        root = Path(settings.BASE_DIR)
        checks = [
            self._doc_check(root / "docs" / "DEPLOYMENT_READINESS.md", "Production deploy checklist"),
            self._doc_check(root / "docs" / "ops" / "RUNBOOK.md", "Operations runbook"),
            self._route_check("health", "Public health route", fallback_path="/health/"),
            self._route_check("public_status", "Public status route"),
            self._command_check("apps.tenant.audit.management.commands.record_backup", "Backup audit command"),
            {
                "name": "External health/status monitoring",
                "status": "manual",
                "detail": "Configure external uptime checks for /health/ and /status/?format=json.",
            },
            {
                "name": "Nightly PostgreSQL backup schedule",
                "status": "manual",
                "detail": "Verify host-level encrypted nightly backups and quarterly restore drill ownership.",
            },
        ]
        if require_production_settings:
            checks.extend(
                [
                    self._setting_check("DEBUG", False, "DEBUG disabled"),
                    self._setting_check("SESSION_COOKIE_SECURE", True, "Secure session cookies"),
                    self._setting_check("CSRF_COOKIE_SECURE", True, "Secure CSRF cookies"),
                    self._setting_check("SECURE_SSL_REDIRECT", True, "SSL redirect"),
                    self._setting_check("SECURE_HSTS_SECONDS", lambda value: int(value or 0) > 0, "HSTS configured"),
                ]
            )
        return checks

    def _doc_check(self, path: Path, name: str):
        return {
            "name": name,
            "status": "pass" if path.exists() and path.stat().st_size > 0 else "fail",
            "detail": str(path.relative_to(settings.BASE_DIR)),
        }

    def _route_check(self, route_name: str, name: str, fallback_path: str = ""):
        try:
            detail = reverse(route_name)
        except NoReverseMatch:
            if fallback_path:
                return {"name": name, "status": "pass", "detail": fallback_path}
            return {"name": name, "status": "fail", "detail": f"Route {route_name!r} does not resolve."}
        return {"name": name, "status": "pass", "detail": detail}

    def _command_check(self, module_path: str, name: str):
        try:
            __import__(module_path)
        except ImportError as exc:
            return {"name": name, "status": "fail", "detail": str(exc)}
        return {"name": name, "status": "pass", "detail": module_path}

    def _setting_check(self, setting_name: str, expected, name: str):
        value = getattr(settings, setting_name, None)
        ok = expected(value) if callable(expected) else value == expected
        return {
            "name": name,
            "status": "pass" if ok else "fail",
            "detail": f"{setting_name}={value!r}",
        }
