import json
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant


class Command(BaseCommand):
    help = "Create two temporary PostgreSQL tenant schemas and verify row isolation."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
        parser.add_argument("--strict", action="store_true", help="Fail when isolation cannot be proved.")

    def handle(self, *args, **options):
        result = self._run_probe()
        if options["json"]:
            self.stdout.write(json.dumps(result, indent=2))
        else:
            self.stdout.write("PostgreSQL tenant isolation probe")
            self.stdout.write("=" * 35)
            for check in result["checks"]:
                self.stdout.write(f"[{check['status'].upper()}] {check['name']}: {check['detail']}")

        if options["strict"] and not result["ok"]:
            failures = ", ".join(item["name"] for item in result["checks"] if item["status"] != "pass")
            raise CommandError(f"Tenant isolation probe failed: {failures}")

    def _run_probe(self):
        if connection.vendor != "postgresql":
            return {
                "ok": False,
                "checks": [self._check("PostgreSQL backend", False, f"connection.vendor={connection.vendor}")],
            }

        suffix = uuid.uuid4().hex[:10]
        tenants = []
        checks = [self._check("PostgreSQL backend", True, "django-tenants PostgreSQL backend is active")]
        try:
            tenant_a = Tenant.objects.create(name="CI Isolation A", schema_name=f"ci_iso_a_{suffix}", status="active")
            tenants.append(tenant_a)
            tenant_b = Tenant.objects.create(name="CI Isolation B", schema_name=f"ci_iso_b_{suffix}", status="active")
            tenants.append(tenant_b)

            user_model = get_user_model()
            username = f"isolation_probe_{suffix}"
            email_a = f"a-{suffix}@isolation.test"
            email_b = f"b-{suffix}@isolation.test"

            with tenant_context(tenant_a):
                user_model.objects.create_user(username=username, email=email_a, password="ci-probe-password")
            with tenant_context(tenant_b):
                user_model.objects.create_user(username=username, email=email_b, password="ci-probe-password")

            with tenant_context(tenant_a):
                rows_a = list(user_model.objects.filter(username=username).values_list("email", flat=True))
            with tenant_context(tenant_b):
                rows_b = list(user_model.objects.filter(username=username).values_list("email", flat=True))

            checks.extend(
                [
                    self._check("Tenant A owns only its row", rows_a == [email_a], f"rows={rows_a!r}"),
                    self._check("Tenant B owns only its row", rows_b == [email_b], f"rows={rows_b!r}"),
                    self._check("Overlapping tenant keys are allowed", len(rows_a) == 1 and len(rows_b) == 1, f"username={username}"),
                    self._check("Schema names are distinct", tenant_a.schema_name != tenant_b.schema_name, f"{tenant_a.schema_name}, {tenant_b.schema_name}"),
                ]
            )
        except Exception as exc:
            checks.append(self._check("Schema creation and tenant writes", False, f"{exc.__class__.__name__}: {exc}"))
        finally:
            connection.set_schema_to_public()
            cleanup_errors = []
            for tenant in reversed(tenants):
                try:
                    tenant.delete(force_drop=True)
                except Exception as exc:
                    cleanup_errors.append(f"{tenant.schema_name}: {exc.__class__.__name__}: {exc}")
            checks.append(
                self._check(
                    "Temporary schema cleanup",
                    not cleanup_errors,
                    "temporary schemas dropped" if not cleanup_errors else "; ".join(cleanup_errors),
                )
            )

        return {"ok": all(item["status"] == "pass" for item in checks), "checks": checks}

    def _check(self, name, ok, detail):
        return {"name": name, "status": "pass" if ok else "fail", "detail": detail}
