"""
Create an illustrative 0–100 letter grading scale suitable for many Ugandan schools.
Does not replace official UNEB tables; admins can edit ranges in Grading Scales.

Run for all tenants:
    python manage.py seed_uganda_grading_scale

Run for one tenant schema:
    python manage.py seed_uganda_grading_scale --schema=mytenant
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from apps.public.tenants.models import Tenant

from apps.tenant.academics.models import GradeRange, GradingScale

SCALE_NAME = "Uganda-style (0–100, illustrative)"
# Typical school-style bands; adjust in admin if your school uses different cut-offs.
BANDS = (
    ("A", Decimal("80"), Decimal("100"), Decimal("5"), 1, "Excellent"),
    ("B", Decimal("70"), Decimal("79.99"), Decimal("4"), 2, "Very good"),
    ("C", Decimal("60"), Decimal("69.99"), Decimal("3"), 3, "Good"),
    ("D", Decimal("50"), Decimal("59.99"), Decimal("2"), 4, "Fair"),
    ("E", Decimal("40"), Decimal("49.99"), Decimal("1"), 5, "Pass"),
    ("F", Decimal("0"), Decimal("39.99"), Decimal("0"), 6, "Fail"),
)


class Command(BaseCommand):
    help = "Add an illustrative Uganda-oriented grading scale (0–100) to each tenant schema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="",
            help="Tenant schema_name to update only (default: all non-public tenants).",
        )

    def handle(self, *args, **options):
        schema_filter = (options.get("schema") or "").strip()
        qs = Tenant.objects.exclude(schema_name="public")
        if schema_filter:
            qs = qs.filter(schema_name=schema_filter)
        tenants = list(qs)
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants matched."))
            return

        for tenant in tenants:
            with schema_context(tenant.schema_name):
                created = self._seed_one()
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"[{tenant.schema_name}] Created grading scale: {SCALE_NAME}")
                    )
                else:
                    self.stdout.write(
                        f"[{tenant.schema_name}] Scale already exists: {SCALE_NAME}"
                    )

    def _seed_one(self) -> bool:
        if GradingScale.objects.filter(name=SCALE_NAME).exists():
            return False
        with transaction.atomic():
            scale = GradingScale.objects.create(
                name=SCALE_NAME,
                description=(
                    "Illustrative 0–100 letter bands common in secondary schools. "
                    "Edit or replace to match your official grading policy."
                ),
                is_default=False,
                is_active=True,
            )
            for grade, lo, hi, gp, order, remark in BANDS:
                GradeRange.objects.create(
                    scale=scale,
                    grade=grade,
                    min_score=lo,
                    max_score=hi,
                    grade_point=gp,
                    remark=remark,
                    order=order,
                )
        return True
