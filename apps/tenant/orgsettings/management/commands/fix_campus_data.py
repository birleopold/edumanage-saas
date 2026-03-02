"""
Management command to automatically fix campus data inconsistencies.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tenant.academics.models import CourseOffering, Enrollment


class Command(BaseCommand):
    help = "Automatically fix campus data inconsistencies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fixed without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        fixed_count = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made\n"))
        else:
            self.stdout.write(self.style.WARNING("Fixing campus data...\n"))

        with transaction.atomic():
            # Fix CourseOfferings without campus
            self.stdout.write("Fixing CourseOfferings...")
            offerings_to_fix = CourseOffering.objects.filter(
                campus__isnull=True,
                class_group__campus__isnull=False
            ).select_related("class_group", "class_group__campus")

            for offering in offerings_to_fix:
                self.stdout.write(
                    f"  Offering {offering.id}: Setting campus to {offering.class_group.campus}"
                )
                if not dry_run:
                    offering.campus = offering.class_group.campus
                    offering.save(update_fields=["campus"])
                fixed_count += 1

            # Fix Enrollments without campus
            self.stdout.write("\nFixing Enrollments...")
            enrollments_to_fix = Enrollment.objects.filter(
                campus__isnull=True
            ).select_related("offering", "offering__campus", "student", "student__campus")

            for enrollment in enrollments_to_fix:
                derived_campus = enrollment.offering.campus or enrollment.student.campus
                if derived_campus:
                    self.stdout.write(
                        f"  Enrollment {enrollment.id}: Setting campus to {derived_campus}"
                    )
                    if not dry_run:
                        enrollment.campus = derived_campus
                        enrollment.save(update_fields=["campus"])
                    fixed_count += 1

            if dry_run:
                # Rollback transaction in dry-run mode
                transaction.set_rollback(True)

        # Summary
        self.stdout.write("\n" + "=" * 50)
        if fixed_count == 0:
            self.stdout.write(
                self.style.SUCCESS("✓ No campus data issues to fix!")
            )
        else:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"Would fix {fixed_count} record(s). Run without --dry-run to apply changes."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Fixed {fixed_count} record(s)!"
                    )
                )
