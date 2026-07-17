import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


CI_GATES = {
    "Django system check": "python manage.py check",
    "Production deploy check": "python manage.py check --deploy",
    "Template route verification": "python verify_routes.py",
    "Django test suite": "python manage.py test",
    "Node production audit": "npm audit --omit=dev",
}

PRODUCTION_SETTINGS = {
    "DEBUG": False,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_SSL_REDIRECT": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "SECURE_REFERRER_POLICY": "same-origin",
    "X_FRAME_OPTIONS": "DENY",
}


class Command(BaseCommand):
    help = "Verify Phase 1 release gates and production hardening evidence."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
        parser.add_argument("--strict", action="store_true", help="Fail when any release gate evidence is missing.")

    def handle(self, *args, **options):
        checks = self._checks()
        summary = {"ok": all(item["status"] == "pass" for item in checks), "checks": checks}

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2))
        else:
            self.stdout.write("Release gate checklist")
            self.stdout.write("=" * 24)
            for item in checks:
                self.stdout.write(f"[{item['status'].upper()}] {item['name']}: {item['detail']}")

        if options["strict"] and not summary["ok"]:
            failing = ", ".join(item["name"] for item in checks if item["status"] != "pass")
            raise CommandError(f"Release gate check failed: {failing}")

    def _checks(self):
        root = Path(settings.BASE_DIR)
        ci = self._read_text(root / ".github" / "workflows" / "ci.yml")
        env_template = self._read_text(root / ".env.production.example")
        checks = [
            self._check(name, command in ci, command)
            for name, command in CI_GATES.items()
        ]
        checks.extend(
            [
                self._check(
                    ".env production settings module",
                    "DJANGO_SETTINGS_MODULE=config.settings.prod" in env_template,
                    "DJANGO_SETTINGS_MODULE=config.settings.prod",
                ),
                self._check(
                    "Production HSTS preload deploy override",
                    'DJANGO_SECURE_HSTS_PRELOAD: "True"' in ci,
                    "CI sets DJANGO_SECURE_HSTS_PRELOAD=True for check --deploy",
                ),
            ]
        )
        checks.extend(self._production_setting_checks())
        return checks

    def _production_setting_checks(self):
        checks = []
        for setting_name, expected in PRODUCTION_SETTINGS.items():
            value = getattr(settings, setting_name, None)
            checks.append(
                self._check(
                    f"Production setting {setting_name}",
                    value == expected,
                    f"{setting_name}={value!r}",
                )
            )
        checks.append(
            self._check(
                "Production HSTS seconds",
                int(getattr(settings, "SECURE_HSTS_SECONDS", 0) or 0) > 0,
                f"SECURE_HSTS_SECONDS={getattr(settings, 'SECURE_HSTS_SECONDS', None)!r}",
            )
        )
        return checks

    def _read_text(self, path):
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _check(self, name, ok, detail):
        return {"name": name, "status": "pass" if ok else "fail", "detail": detail}
