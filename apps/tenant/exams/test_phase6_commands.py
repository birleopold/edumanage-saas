from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class Phase6ExternalExaminationCommandTests(TestCase):
    def test_bootstrap_rejects_unknown_tenant_schema(self):
        with self.assertRaises(CommandError):
            call_command(
                "bootstrap_external_exam_candidates",
                schema="missing-phase6-schema",
                verbosity=0,
            )

    def test_audit_rejects_unknown_tenant_schema(self):
        with self.assertRaises(CommandError):
            call_command(
                "audit_external_exams",
                schema="missing-phase6-schema",
                verbosity=0,
            )
