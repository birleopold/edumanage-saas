from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant
from apps.tenant.hr.models import StaffProfile
from apps.tenant.users.models import Role

from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.teachers.sync import ensure_staff_for_teacher, ensure_teacher_for_staff


class Command(BaseCommand):
    help = "Normalize teacher academic profiles and HR staff records across school tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            help="Normalize one tenant schema only, for example demo.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")

        total_teachers = 0
        total_staff = 0

        for tenant in tenants:
            with tenant_context(tenant), transaction.atomic():
                teacher_count = 0
                staff_count = 0

                for teacher in TeacherProfile.objects.select_related("user", "campus").all():
                    ensure_staff_for_teacher(teacher)
                    teacher_count += 1

                teaching_staff = (
                    StaffProfile.objects.select_related("user", "campus")
                    .filter(
                        Q(staff_category=StaffProfile.TEACHING)
                        | Q(user__roles__code=Role.TEACHER)
                    )
                    .distinct()
                )
                for staff in teaching_staff:
                    ensure_teacher_for_staff(staff)
                    staff_count += 1

                total_teachers += teacher_count
                total_staff += staff_count
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{tenant.schema_name}: normalized {teacher_count} teacher profile(s) "
                        f"and {staff_count} teaching staff record(s)."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed normalization: {total_teachers} teacher profile(s), "
                f"{total_staff} teaching staff record(s)."
            )
        )
