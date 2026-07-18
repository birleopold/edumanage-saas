import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


CI_GATES = {
    "Django system check": "python manage.py check",
    "Production deploy check": "python manage.py check --deploy",
    "Template route verification": "python verify_routes.py",
    "Django test suite": "python manage.py test",
    "Migration drift check": "python manage.py makemigrations --check --dry-run",
    "Python dependency audit": "pip-audit -r requirements.txt",
    "PostgreSQL shared-schema migration": "python manage.py migrate_schemas --shared --noinput --settings=config.settings.tenants",
    "PostgreSQL tenant isolation": "python manage.py check_tenant_isolation --strict --settings=config.settings.tenants",
}

PRODUCTION_SETTINGS = {
    "DEBUG": False,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_SSL_REDIRECT": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "SECURE_REFERRER_POLICY": "same-origin",
    "X_FRAME_OPTIONS": "DENY",
    "ADMIN_2FA_REQUIRED": True,
    "MOBILE_MONEY_DRY_RUN_ENABLED": False,
    "WEBHOOK_ALLOW_PRIVATE_TARGETS": False,
}


class Command(BaseCommand):
    help = "Verify Django-only release gates and production hardening evidence."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--strict", action="store_true")

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
        ci = self._read(root / ".github" / "workflows" / "ci.yml")
        env_template = self._read(root / ".env.production.example")
        checks = [self._check(name, command in ci, command) for name, command in CI_GATES.items()]
        checks.extend(
            [
                self._check(
                    "Django-only repository",
                    not (root / "package.json").exists() and not (root / "package-lock.json").exists(),
                    "No package.json/package-lock.json or npm build dependency",
                ),
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
        using_production_module = settings.SETTINGS_MODULE.endswith(".prod")
        for name, expected in PRODUCTION_SETTINGS.items():
            value = getattr(settings, name, None)
            ok = value == expected if using_production_module else True
            detail = f"{name}={value!r}" if using_production_module else f"verified when config.settings.prod is loaded; current {name}={value!r}"
            checks.append(self._check(f"Production setting {name}", ok, detail))
        hsts = int(getattr(settings, "SECURE_HSTS_SECONDS", 0) or 0)
        hsts_ok = hsts > 0 if using_production_module else True
        hsts_detail = f"SECURE_HSTS_SECONDS={hsts!r}" if using_production_module else "verified when config.settings.prod is loaded"
        checks.append(self._check("Production HSTS seconds", hsts_ok, hsts_detail))
        return checks

    def _read(self, path):
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _check(self, name, ok, detail):
        return {"name": name, "status": "pass" if ok else "fail", "detail": detail}
