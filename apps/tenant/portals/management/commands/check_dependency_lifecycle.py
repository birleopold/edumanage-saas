import json
import sys
from importlib import metadata
from pathlib import Path

from django import get_version as get_django_version
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

SUPPORTED_DJANGO_LTS = "5.2"
SUPPORTED_DJANGO_UNTIL = "April 2028"
MIN_DJANGO_TENANTS_FOR_DJANGO_52 = (3, 10, 2)
SUPPORTED_PYTHON_MIN = (3, 11)

class Command(BaseCommand):
    help = "Verify Django and Python dependency lifecycle gates for release readiness."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
        parser.add_argument("--strict", action="store_true", help="Fail when any lifecycle check fails.")

    def handle(self, *args, **options):
        checks = self._checks()
        summary = {"ok": all(item["status"] == "pass" for item in checks), "checks": checks, "policy": {"django_lts_target": SUPPORTED_DJANGO_LTS, "django_lts_supported_until": SUPPORTED_DJANGO_UNTIL, "monthly_review_doc": "docs/ops/DEPENDENCY_LIFECYCLE.md", "asset_strategy": "Django static files only; no npm runtime or build requirement"}}
        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2))
        else:
            self.stdout.write("Dependency lifecycle checklist")
            self.stdout.write("=" * 32)
            for item in checks:
                self.stdout.write(f"[{item['status'].upper()}] {item['name']}: {item['detail']}")
        if options["strict"] and not summary["ok"]:
            failing = ", ".join(item["name"] for item in checks if item["status"] != "pass")
            raise CommandError(f"Dependency lifecycle check failed: {failing}")

    def _checks(self):
        root = Path(settings.BASE_DIR)
        requirements = self._read_text(root / "requirements.txt")
        ci = self._read_text(root / ".github" / "workflows" / "ci.yml")
        doc = root / "docs" / "ops" / "DEPENDENCY_LIFECYCLE.md"
        django_version = get_django_version()
        django_tenants_version = self._package_version("django-tenants")
        return [
            self._check("Django LTS pin", django_version.startswith(f"{SUPPORTED_DJANGO_LTS}.") and f"Django=={SUPPORTED_DJANGO_LTS}." in requirements, f"installed={django_version}, target={SUPPORTED_DJANGO_LTS} LTS supported until {SUPPORTED_DJANGO_UNTIL}"),
            self._check("django-tenants compatibility", self._version_tuple(django_tenants_version) >= MIN_DJANGO_TENANTS_FOR_DJANGO_52, f"installed={django_tenants_version}, required>=3.10.2 for Django 5.2+ classifiers"),
            self._check("Python runtime pin", sys.version_info[:2] >= SUPPORTED_PYTHON_MIN and 'python-version: "3.11"' in ci, f"runtime={sys.version_info.major}.{sys.version_info.minor}, ci=3.11"),
            self._check("Django-only asset strategy", not (root / "package.json").exists() and not (root / "package-lock.json").exists(), "repository has no npm dependency or build requirement"),
            self._check("Python dependency audit gate", "pip-audit -r requirements.txt" in ci, "CI audits Python dependencies with pip-audit"),
            self._check("CI dependency lifecycle gate", "check_dependency_lifecycle --strict" in ci, "CI runs python manage.py check_dependency_lifecycle --strict"),
            self._check("Monthly review procedure", doc.exists() and "Monthly dependency review" in doc.read_text(encoding="utf-8"), "docs/ops/DEPENDENCY_LIFECYCLE.md records owner, cadence and release-note review steps"),
        ]

    def _check(self, name, ok, detail):
        return {"name": name, "status": "pass" if ok else "fail", "detail": detail}

    def _read_text(self, path):
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _package_version(self, package):
        try:
            return metadata.version(package)
        except metadata.PackageNotFoundError:
            return "0"

    def _version_tuple(self, version):
        parts = []
        for part in version.split("."):
            digits = "".join(char for char in part if char.isdigit())
            if not digits:
                break
            parts.append(int(digits))
        return tuple(parts)
