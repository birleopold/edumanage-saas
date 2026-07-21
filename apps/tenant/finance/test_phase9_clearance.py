from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Level, Program, Stream
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile

from .clearance_models import ClearanceDecisionLog, ClearanceOverride, ClearancePolicy
from .clearance_services import (
    bootstrap_policy_templates,
    clearance_readiness,
    evaluate_clearance,
    resolve_clearance_policy,
)
from .models import Invoice, InvoiceLine, Payment


class Phase9ClearanceServiceTests(TestCase):
    def setUp(self):
        organization = OrganizationProfile.objects.create(name="Phase 9 School")
        self.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.year = AcademicYear.objects.create(name="2029", is_current=True)
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1, is_current=True)
        self.other_term = AcademicTerm.objects.create(year=self.year, name="Term 2", order=2)
        self.level = Level.objects.create(name="Senior Four", order=4)
        self.program = Program.objects.create(name="Secondary", code="SEC")
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior Four",
            level=self.level,
            program=self.program,
        )
        self.stream = Stream.objects.create(class_group=self.class_group, name="A")
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="P9-001",
            first_name="Amina",
            last_name="Learner",
        )
        self.invoice = Invoice.objects.create(
            student=self.student,
            academic_year=self.year,
            academic_term=self.term,
            reference="P9-T1",
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            description="Tuition",
            quantity=1,
            unit_amount=Decimal("1000.00"),
        )
        self.payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("400.00"),
            method=Payment.CASH,
        )

    def policy(self, **kwargs):
        defaults = {
            "code": f"POL-{ClearancePolicy.objects.count() + 1}",
            "name": "Results clearance",
            "access_type": ClearancePolicy.ASSESSMENT_RESULTS,
            "academic_term": self.term,
            "rule_type": ClearancePolicy.FULL_PAYMENT,
            "enforcement_mode": ClearancePolicy.BLOCK,
            "allow_when_no_invoice": True,
            "is_active": True,
        }
        defaults.update(kwargs)
        return ClearancePolicy.objects.create(**defaults)

    def test_no_matching_policy_defaults_to_allowed_access(self):
        decision = evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term)
        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.policy)
        self.assertEqual(decision.decision_code, ClearanceDecisionLog.ALLOWED)

    def test_full_payment_policy_blocks_using_live_invoice_and_payment_totals(self):
        self.policy()
        invoice_count = Invoice.objects.count()
        payment_count = Payment.objects.count()

        decision = evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term)

        self.assertTrue(decision.blocked)
        self.assertEqual(decision.finance.invoiced_amount, Decimal("1000.00"))
        self.assertEqual(decision.finance.paid_amount, Decimal("400.00"))
        self.assertEqual(decision.finance.outstanding_balance, Decimal("600.00"))
        self.assertEqual(Invoice.objects.count(), invoice_count)
        self.assertEqual(Payment.objects.count(), payment_count)

    def test_advisory_policy_warns_but_does_not_block(self):
        self.policy(enforcement_mode=ClearancePolicy.ADVISORY)
        decision = evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term)
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.advisory)
        self.assertEqual(decision.decision_code, ClearanceDecisionLog.ADVISED)

    def test_minimum_percentage_and_maximum_balance_rules(self):
        percentage_policy = self.policy(
            code="MIN-PERCENT",
            rule_type=ClearancePolicy.MINIMUM_PERCENTAGE,
            minimum_paid_percentage=Decimal("50.00"),
        )
        decision = evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term)
        self.assertTrue(decision.blocked)
        percentage_policy.minimum_paid_percentage = Decimal("40.00")
        percentage_policy.save()
        self.assertTrue(evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term).allowed)

        percentage_policy.is_active = False
        percentage_policy.save()
        self.policy(
            code="MAX-BALANCE",
            rule_type=ClearancePolicy.MAXIMUM_BALANCE,
            maximum_outstanding_balance=Decimal("600.00"),
        )
        self.assertTrue(evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term).allowed)

    def test_policy_resolution_prefers_more_specific_scope_at_same_priority(self):
        global_policy = self.policy(code="GLOBAL", academic_term=None, priority=10)
        campus_policy = self.policy(code="CAMPUS", campus=self.campus, priority=10)
        resolved = resolve_clearance_policy(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term)
        self.assertEqual(resolved, campus_policy)
        self.assertNotEqual(resolved, global_policy)

    def test_current_term_basis_does_not_include_other_term_invoice(self):
        other_invoice = Invoice.objects.create(
            student=self.student,
            academic_year=self.year,
            academic_term=self.other_term,
            reference="P9-T2",
        )
        InvoiceLine.objects.create(
            invoice=other_invoice,
            description="Other term",
            quantity=1,
            unit_amount=Decimal("5000.00"),
        )
        self.policy(rule_type=ClearancePolicy.MAXIMUM_BALANCE, maximum_outstanding_balance=Decimal("600.00"))
        decision = evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.finance.invoiced_amount, Decimal("1000.00"))

    def test_valid_override_grants_access_without_changing_finance_records(self):
        policy = self.policy()
        override = ClearanceOverride.objects.create(
            student=self.student,
            policy=policy,
            access_type=ClearancePolicy.ASSESSMENT_RESULTS,
            academic_term=self.term,
            valid_from=timezone.localdate(),
            valid_until=timezone.localdate() + timedelta(days=7),
            reason="Payment verification pending",
            approved_by=get_user_model().objects.create_superuser(
                username="phase9approver",
                email="phase9@example.com",
                password="test-password",
            ),
        )
        decision = evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.override, override)
        self.assertEqual(decision.decision_code, ClearanceDecisionLog.OVERRIDDEN)
        self.assertEqual(self.invoice.balance(), Decimal("600.00"))

    def test_expired_override_does_not_grant_access(self):
        policy = self.policy()
        ClearanceOverride.objects.create(
            student=self.student,
            policy=policy,
            access_type=ClearancePolicy.ASSESSMENT_RESULTS,
            academic_term=self.term,
            valid_from=timezone.localdate() - timedelta(days=10),
            valid_until=timezone.localdate() - timedelta(days=1),
            reason="Expired exception",
        )
        self.assertTrue(evaluate_clearance(self.student, ClearancePolicy.ASSESSMENT_RESULTS, self.term).blocked)

    def test_bootstrap_is_dry_run_first_inactive_and_idempotent(self):
        preview = bootstrap_policy_templates(apply=False)
        self.assertEqual(len(preview), 5)
        self.assertEqual(ClearancePolicy.objects.count(), 0)
        bootstrap_policy_templates(apply=True)
        bootstrap_policy_templates(apply=True)
        self.assertEqual(ClearancePolicy.objects.count(), 5)
        self.assertFalse(ClearancePolicy.objects.filter(is_active=True).exists())
        self.assertTrue(evaluate_clearance(self.student, ClearancePolicy.ONLINE_EXAM, self.term).allowed)

    def test_readiness_is_read_only(self):
        self.policy()
        invoice_count = Invoice.objects.count()
        payment_count = Payment.objects.count()
        readiness = clearance_readiness()
        self.assertTrue(readiness["ready"])
        self.assertEqual(Invoice.objects.count(), invoice_count)
        self.assertEqual(Payment.objects.count(), payment_count)
