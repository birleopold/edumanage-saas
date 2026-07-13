import json

from django.core.management.base import BaseCommand, CommandError

from apps.tenant.portals.experience_services import build_school_health_score


class Command(BaseCommand):
    help = "Print the school setup health score and optionally fail below a minimum readiness percentage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-percent",
            type=int,
            default=None,
            help="Exit with an error when the health score is below this percentage.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the complete health score payload as JSON.",
        )
        parser.add_argument(
            "--show-complete",
            action="store_true",
            help="Include ready categories in the text report.",
        )

    def handle(self, *args, **options):
        health = build_school_health_score()
        min_percent = options["min_percent"]

        if options["json"]:
            self.stdout.write(json.dumps(health, indent=2, default=str))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"School setup health: {health['percent']}% ({health['level']}) "
                    f"- {health['score']}/{health['possible']} points"
                )
            )
            for item in health["items"]:
                if item["status"] == "complete" and not options["show_complete"]:
                    continue
                marker = "OK" if item["status"] == "complete" else "!!" if item["status"] == "missing" else ".."
                self.stdout.write(f"{marker} {item['title']}: {item['score']}/{item['weight']} points")
                if item["status"] != "complete":
                    self.stdout.write(f"   Next: {item['next_step']}")

        if min_percent is not None and health["percent"] < min_percent:
            raise CommandError(
                f"School setup health is {health['percent']}%, below required {min_percent}%."
            )
