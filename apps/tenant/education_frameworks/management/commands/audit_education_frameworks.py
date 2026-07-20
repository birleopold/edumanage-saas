from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant
from apps.tenant.orgsettings.services import get_organization

from ...configuration import framework_readiness
from ...models import InstitutionEducationProfile


class Command(BaseCommand):
    help = (
        "Run a read-only education framework readiness audit for one or all "
        "school tenants."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            help="Audit one tenant schema only, for example demo.",
        )
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help=(
                "Return a non-zero exit code when a tenant's Phase 1 "
                "framework setup is incomplete."
            ),
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        fail_on_incomplete = bool(options.get("fail_on_incomplete"))
        tenants = Tenant.objects.exclude(
            schema_name="public"
        ).order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(
                    f"Tenant schema '{schema}' was not found."
                )

        audited = 0
        incomplete = 0
        for tenant in tenants:
            audited += 1
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Tenant: {tenant.schema_name}"
                )
            )
            with tenant_context(tenant):
                organization = get_organization()
                profile = None
                if organization is not None:
                    profile = InstitutionEducationProfile.objects.select_related(
                        "primary_framework",
                        "organization",
                    ).filter(organization=organization).first()

                if profile is None:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "No institution education profile exists. Run "
                            "bootstrap_education_frameworks first."
                        )
                    )
                    continue

                readiness = framework_readiness(profile)
                self.stdout.write(
                    f"Framework: {profile.primary_framework or 'Not selected'}; "
                    f"readiness: {readiness['completion_percent']}% "
                    f"({readiness['completed_checks']}/"
                    f"{readiness['total_checks']} checks)."
                )
                self.stdout.write(
                    f"Campuses fully configured: "
                    f"{readiness['configured_campuses']}/"
                    f"{readiness['campus_count']}; "
                    f"missing campus-stage records: "
                    f"{readiness['missing_campus_stage_count']}."
                )
                self.stdout.write(
                    f"Levels mapped: {readiness['mapped_level_count']}/"
                    f"{readiness['level_count']}; "
                    f"unmapped: {readiness['unmapped_level_count']}; "
                    f"orphaned mappings: "
                    f"{readiness['orphaned_mapping_count']}."
                )
                self.stdout.write(
                    f"Invalid grading links: "
                    f"{readiness['invalid_grading_link_count']}; "
                    f"wrong-framework links: "
                    f"{readiness['framework_mismatch_count']}; "
                    f"wrong-stage links: "
                    f"{readiness['stage_mismatch_count']}; "
                    f"unsupported stages: "
                    f"{readiness['unsupported_stage_link_count']}."
                )

                if readiness["completion_percent"] == 100:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Phase 1 framework setup is ready."
                        )
                    )
                else:
                    incomplete += 1
                    failed_checks = ", ".join(
                        key
                        for key, value in readiness["checks"].items()
                        if not value
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 1 framework setup needs attention: "
                            f"{failed_checks}. No data was changed."
                        )
                    )

        self.stdout.write("")
        self.stdout.write(
            f"Audit complete: {audited} tenant(s), "
            f"{incomplete} incomplete. No data was changed."
        )
        if fail_on_incomplete and incomplete:
            raise CommandError(
                "Education framework audit found "
                f"{incomplete} incomplete tenant(s)."
            )
