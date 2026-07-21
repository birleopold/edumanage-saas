from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class LearningActivityCommandTests(TestCase):
    def test_bootstrap_rejects_unknown_tenant_schema(self):
        with self.assertRaises(CommandError):
            call_command("bootstrap_learning_activities", schema="missing-phase3-schema", verbosity=0)

    def test_audit_rejects_unknown_tenant_schema(self):
        with self.assertRaises(CommandError):
            call_command("audit_learning_activities", schema="missing-phase3-schema", verbosity=0)
