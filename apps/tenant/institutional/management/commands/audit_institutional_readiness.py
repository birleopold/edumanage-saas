from django.core.management.base import BaseCommand, CommandError

from apps.tenant.students.models import StudentProfile

from ...models import CandidateDossier, ReportTemplate, ResultPolicy, VerifiablePermit, VisitationWindow


class Command(BaseCommand):
    help = "Audit institutional education readiness without changing tenant data."

    def add_arguments(self, parser):
        parser.add_argument("--fail-on-incomplete", action="store_true")

    def handle(self, *args, **options):
        checks = {
            "active_report_templates": ReportTemplate.objects.filter(is_active=True).count(),
            "active_result_policies": ResultPolicy.objects.filter(is_active=True).count(),
            "candidate_dossiers": CandidateDossier.objects.count(),
            "valid_permits": sum(1 for permit in VerifiablePermit.objects.filter(status=VerifiablePermit.ACTIVE) if permit.is_valid),
            "active_visitation_windows": VisitationWindow.objects.filter(is_active=True).count(),
            "active_students": StudentProfile.objects.filter(is_active=True).count(),
        }
        for key, value in checks.items():
            self.stdout.write(f"{key}: {value}")

        required = ("active_report_templates", "active_result_policies")
        missing = [key for key in required if checks[key] == 0]
        if missing:
            message = "Institutional readiness is incomplete: " + ", ".join(missing)
            if options["fail_on_incomplete"]:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS("Institutional readiness checks passed."))
