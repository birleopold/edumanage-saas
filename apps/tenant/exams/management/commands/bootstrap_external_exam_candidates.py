from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...external_models import ExternalExamSession
from ...external_services import register_compulsory_subjects, register_eligible_candidates


class Command(BaseCommand):
    help = "Preview or explicitly register eligible Phase 6 candidates and compulsory external subjects."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Run for one tenant schema only.")
        parser.add_argument("--session", help="Limit to one external session code.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write candidate registrations. Without this flag the command is always a dry run.",
        )
        parser.add_argument(
            "--include-compulsory-subjects",
            action="store_true",
            help="Also add missing compulsory subject registrations for existing and newly created candidates.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        session_code = (options.get("session") or "").strip().upper()
        apply_changes = bool(options.get("apply"))
        include_subjects = bool(options.get("include_compulsory_subjects"))

        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")

        processed = 0
        for tenant in tenants:
            with tenant_context(tenant):
                sessions = ExternalExamSession.objects.filter(is_active=True).order_by(
                    "-academic_year__name", "board__name", "name"
                )
                if session_code:
                    sessions = sessions.filter(code=session_code)
                if not sessions.exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"Tenant {tenant.schema_name}: no matching active external examination session."
                        )
                    )
                    continue
                for session in sessions:
                    processed += 1
                    self.stdout.write(
                        self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}; session: {session.code}")
                    )
                    try:
                        candidate_summary = register_eligible_candidates(
                            session,
                            dry_run=not apply_changes,
                        )
                    except ValidationError as exc:
                        self.stdout.write(self.style.WARNING(" ".join(exc.messages)))
                        continue
                    self.stdout.write(
                        f"Eligible: {candidate_summary['eligible_count']}; existing: "
                        f"{candidate_summary['existing_count']}; "
                        f"{'created' if apply_changes else 'would create'}: "
                        f"{candidate_summary['created_count']}."
                    )
                    if include_subjects:
                        subject_summary = register_compulsory_subjects(
                            session,
                            dry_run=not apply_changes,
                        )
                        self.stdout.write(
                            f"Compulsory registrations existing: {subject_summary['existing_count']}; "
                            f"{'created' if apply_changes else 'would create'}: "
                            f"{subject_summary['created_count']}."
                        )
                    if apply_changes:
                        self.stdout.write(
                            self.style.SUCCESS(
                                "Candidate bootstrap applied. Internal exams, scores, enrollments and learner placement were unchanged."
                            )
                        )
                    else:
                        self.stdout.write(self.style.SUCCESS("Dry run complete; no data changed."))

        if processed == 0 and session_code:
            raise CommandError(f"No active external session with code '{session_code}' was found.")
