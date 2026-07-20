from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...models import Assessment, AssessmentType
from ...services import (
    ASSESSMENT_TYPE_TEMPLATES,
    classify_existing_records,
    ensure_assessment_type_templates,
    create_missing_exam_paper_links,
)


class Command(BaseCommand):
    help = "Seed assessment type templates and safely classify existing assessments and exam papers."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Run for one tenant schema only.")
        parser.add_argument("--classify-existing", action="store_true", help="Attach types and matching components to existing records.")
        parser.add_argument("--skip-exam-papers", action="store_true", help="Do not classify exam papers.")
        parser.add_argument("--create-exam-links", action="store_true", help="Create metadata-only Assessment links for exam papers; exam scores are not copied.")
        parser.add_argument("--dry-run", action="store_true", help="Report intended changes without writing data.")

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
+            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")
        dry_run = bool(options.get("dry_run"))
        for tenant in tenants:
            with tenant_context(tenant):
                existing_codes = set(AssessmentType.objects.values_list("code", flat=True))
                template_codes = {item[0] for item in ASSESSMENT_TYPE_TEMPLATES}
                missing_codes = sorted(template_codes - existing_codes)
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(f"Assessment type templates missing: {len(missing_codes)}")
                if missing_codes:
                    self.stdout.write("  " + ", ".join(missing_codes))
                if not dry_run:
                    ensure_assessment_type_templates()
                if options.get("classify_existing"):
                    if dry_run and missing_codes:
                        self.stdout.write(self.style.WARNING("Classification preview skipped because required templates do not yet exist."))
                    else:
                        summary = classify_existing_records(
                            dry_run=dry_run,
                            include_exam_papers=not options.get("skip_exam_papers"),
                        )
                        self.stdout.write(
                            "Classification: "
                            f"assessments={summary['assessments_classified']}, "
                            f"exam papers={summary['exam_papers_classified']}, "
                            f"component links={summary['assessments_linked'] + summary['exam_papers_linked']}."
                        )
                if options.get("create_exam_links"):
                    links = create_missing_exam_paper_links(dry_run=dry_run)
                    self.stdout.write(
                        f"Exam-paper compatibility links: {links['created']} to create, {links['existing']} already present."
                    )
                self.stdout.write(
                    self.style.SUCCESS(
                        "Dry run complete; no data changed." if dry_run else "Assessment framework bootstrap complete. Existing scores and legacy weights were not changed."
                    )
                )
