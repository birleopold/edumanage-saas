from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus

from ...device_services import finalize_absences
from ...models import AttendanceIdentity


class Command(BaseCommand):
    help = "Finalize missing device-presence records as absent for configured attendance policies."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="day", help="YYYY-MM-DD. Defaults to today.")
        parser.add_argument("--campus", dest="campus", help="Campus ID or code. Omit to process all active campuses.")
        parser.add_argument(
            "--person-type",
            choices=[AttendanceIdentity.STUDENT, AttendanceIdentity.STAFF, "ALL"],
            default="ALL",
            help="Which register to finalize.",
        )
        parser.add_argument(
            "--previous-day",
            action="store_true",
            help="Finalize yesterday instead of today; useful for overnight scheduled jobs.",
        )

    def handle(self, *args, **options):
        if options.get("day"):
            try:
                day = date.fromisoformat(options["day"])
            except ValueError as exc:
                raise CommandError("--date must use YYYY-MM-DD.") from exc
        else:
            day = timezone.localdate()
            if options.get("previous_day"):
                day -= timedelta(days=1)

        campuses = Campus.objects.filter(is_active=True).order_by("organization_id", "name")
        campus_ref = (options.get("campus") or "").strip()
        if campus_ref:
            if campus_ref.isdigit():
                campuses = campuses.filter(pk=int(campus_ref))
            else:
                campuses = campuses.filter(code=campus_ref)
        if not campuses.exists():
            raise CommandError("No active campus matched the requested scope.")

        person_types = (
            [AttendanceIdentity.STUDENT, AttendanceIdentity.STAFF]
            if options["person_type"] == "ALL"
            else [options["person_type"]]
        )
        total = 0
        skipped = 0
        for campus in campuses:
            for person_type in person_types:
                result = finalize_absences(day=day, campus=campus, person_type=person_type)
                total += result["created"]
                skipped += int(result["skipped"])
                label = f"{campus} / {person_type}"
                if result["skipped"]:
                    self.stdout.write(self.style.WARNING(f"{label}: skipped — {result['reason']}"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"{label}: created {result['created']} absence record(s)"))

        self.stdout.write(self.style.SUCCESS(f"Finalization complete for {day}: {total} absence record(s), {skipped} skipped policy scope(s)."))
