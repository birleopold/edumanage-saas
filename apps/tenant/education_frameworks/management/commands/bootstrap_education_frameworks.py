from django.core.management.base import BaseCommand, CommandError

from apps.tenant.academics.models import Level
from apps.tenant.orgsettings.models import OrganizationProfile

from ...models import InstitutionEducationProfile
from ...services import (
    enable_mapped_stages,
    ensure_institution_profile,
    ensure_system_templates,
    infer_stage_code,
    map_existing_levels,
)


class Command(BaseCommand):
    help = (
        "Create or refresh education framework templates and map existing "
        "academic levels without changing them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-id",
            type=int,
            help="Organization profile ID. Defaults to the first organization.",
        )
        parser.add_argument(
            "--country-code",
            default="UG",
            help="Two-letter country code. Defaults to UG.",
        )
        parser.add_argument(
            "--locale",
            default="en-UG",
            help="Locale code. Defaults to en-UG.",
        )
        parser.add_argument(
            "--institution-type",
            choices=[
                choice[0]
                for choice in InstitutionEducationProfile.INSTITUTION_TYPE_CHOICES
            ],
            default=InstitutionEducationProfile.MIXED,
        )
        parser.add_argument(
            "--map-levels",
            action="store_true",
            help="Map existing academics.Level records to education stages.",
        )
        parser.add_argument(
            "--enable-mapped-stages",
            action="store_true",
            help=(
                "Enable mapped education stages for every active campus in "
                "the organization."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the proposed mapping without changing data.",
        )

    def handle(self, *args, **options):
        country_code = (options.get("country_code") or "").strip().upper()
        if len(country_code) != 2 or not country_code.isalpha():
            raise CommandError(
                "--country-code must be a two-letter alphabetic code, for example UG."
            )
        locale = (options.get("locale") or "").strip()
        if not locale:
            raise CommandError("--locale cannot be blank.")

        organization_id = options.get("organization_id")
        if organization_id is not None:
            organization = OrganizationProfile.objects.filter(
                pk=organization_id
            ).first()
            if organization is None:
                raise CommandError(
                    f"Organization profile {organization_id} was not found in this tenant."
                )
        else:
            organization = OrganizationProfile.objects.order_by("pk").first()
        if organization is None:
            raise CommandError(
                "No organization profile exists in this tenant."
            )

        dry_run = bool(options.get("dry_run"))
        if dry_run:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Education framework dry run: {organization}"
                )
            )
            self.stdout.write(
                f"Profile defaults: country={country_code}, locale={locale}, "
                f"type={options['institution_type']}"
            )
            existing_profile = InstitutionEducationProfile.objects.filter(
                organization=organization
            ).first()
            if existing_profile is not None:
                self.stdout.write(
                    "An institution education profile already exists; its "
                    "saved profile fields would remain unchanged."
                )
            if options.get("map_levels"):
                for level in Level.objects.all().order_by("order", "name"):
                    self.stdout.write(
                        f"  {level.pk}: {level.name} -> "
                        f"{infer_stage_code(level.name)}"
                    )
            if options.get("enable_mapped_stages"):
                self.stdout.write(
                    "Mapped stages would be enabled for each active campus "
                    "after level mapping."
                )
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. No data was changed."
                )
            )
            return

        stages, frameworks = ensure_system_templates()
        profile = ensure_institution_profile(
            organization,
            country_code=country_code,
            locale=locale,
            institution_type=options["institution_type"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Education profile ready for {organization}."
            )
        )
        self.stdout.write(
            f"Templates: {len(stages)} education stages, "
            f"{len(frameworks)} academic frameworks."
        )

        if options.get("map_levels") or options.get("enable_mapped_stages"):
            summary = map_existing_levels(profile)
            self.stdout.write(
                "Level mappings: "
                f"{summary['created']} created, "
                f"{summary['updated']} updated, "
                f"{summary['unchanged']} unchanged, "
                f"{summary['manual_preserved']} administrator correction(s) preserved."
            )

        if options.get("enable_mapped_stages"):
            created = enable_mapped_stages(profile)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Enabled {created} new campus education stage "
                    "configuration(s)."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Education framework bootstrap complete. Existing academic "
                "levels and records were not modified."
            )
        )
