from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...models import Assessment, AssessmentType
from ...services import assessment_framework_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 2 assessment framework audit for one or all school tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument("--fail-on-incomplete", action="store_true", help="Return a non-zero exit code if Phase 2 configuration is incomplete.")

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")
        incomplete = 0
        audited = 0
        for tenant in tenants:
            audited += 1
            with tenant_context(tenant):
                readiness = assessment_framework_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Types: {AssessmentType.objects.filter(is_active=True).count()}; "
                    f"schemes: {readiness['scheme_count']}; invalid schemes: {readiness['invalid_scheme_count']}."
                )
                self.stdout.write(
                    f"Assessments classified: {readiness['classified_assessment_count']}/{readiness['assessment_count']}; "
                    f"inactive links: {readiness['inactive_link_count']}; mismatched links: {readiness['mismatched_link_count']}."
                )
                try:
                    from apps.tenant.exams.models import ExamPaper

                    exam_link_issues = ExamPaper.objects.filter(
                        Q(assessment_type__is_active=False)
                        | Q(weighting_component__is_active=False)
                        | Q(weighting_component__scheme__is_active=False)
                    ).distinct().count()
                    exam_link_issues += ExamPaper.objects.filter(
                        assessment_type__isnull=False,
                        weighting_component__isnull=False,
                    ).exclude(assessment_type_id=F("weighting_component__assessment_type_id")).count()
                except Exception:
                    exam_link_issues = 0
                if readiness["ready"] and exam_link_issues == 0:
                    self.stdout.write(self.style.SUCCESS("Phase 2 assessment framework is structurally ready."))
                else:
                    incomplete += 1
                    self.stdout.write(self.style.WARNING(f"Phase 2 needs attention. Exam-paper link issues: {exam_link_issues}. No data was changed."))
        self.stdout.write(f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed.")
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"Assessment framework audit found {incomplete} incomplete tenant(s).")
