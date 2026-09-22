from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.management import call_command
from io import StringIO

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import AssetAssignment, InventoryItem, StockMovement


class InventoryAssignmentCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Inventory Campus",
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Asset",
            student_id="INV-VISIBLE",
            campus=self.campus,
            is_active=True,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Asset",
            student_id="INV-HIDDEN",
            campus=self.other_campus,
            is_active=True,
        )
        self.item = InventoryItem.objects.create(name="Tablet", sku="TAB-1", unit="pcs", is_active=True)
        StockMovement.objects.create(item=self.item, movement_type=StockMovement.IN, quantity=Decimal("10"))
        self.assignment = AssetAssignment.objects.create(
            item=self.item,
            quantity=Decimal("1"),
            assigned_to_student=self.student,
            assigned_at=date(2026, 1, 1),
            status=AssetAssignment.ACTIVE,
        )
        self.hidden_assignment = AssetAssignment.objects.create(
            item=self.item,
            quantity=Decimal("1"),
            assigned_to_student=self.hidden_student,
            assigned_at=date(2026, 1, 1),
            status=AssetAssignment.ACTIVE,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="inventory_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_assignment_list_sees_own_students_only(self):
        self.client.login(username="inventory_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_inventory_assignments_list"))

        self.assertEqual(response.status_code, 200)
        assignment_ids = {assignment.pk for assignment in response.context["assignments"]}
        self.assertIn(self.assignment.pk, assignment_ids)
        self.assertNotIn(self.hidden_assignment.pk, assignment_ids)

    def test_campus_admin_dashboard_counts_scoped_assignments(self):
        self.client.login(username="inventory_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_inventory_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assignment_count"], 1)
        assignment_ids = {assignment.pk for assignment in response.context["recent_assignments"]}
        self.assertIn(self.assignment.pk, assignment_ids)
        self.assertNotIn(self.hidden_assignment.pk, assignment_ids)

    def test_multi_campus_admin_sees_assignments_from_every_assigned_campus(self):
        campus_role = Role.objects.get(code=Role.CAMPUS_ADMIN)
        UserRole.objects.create(
            user=self.user, role=campus_role, campus=self.other_campus
        )
        self.client.login(username="inventory_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_inventory_assignments_list"))

        assignment_ids = {assignment.pk for assignment in response.context["assignments"]}
        self.assertEqual(assignment_ids, {self.assignment.pk, self.hidden_assignment.pk})

    def test_campus_admin_cannot_create_assignment_for_other_campus_student(self):
        self.hidden_assignment.delete()
        self.client.login(username="inventory_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_inventory_assignments_create"),
            {
                "item": self.item.pk,
                "quantity": "1",
                "assigned_to_user": "",
                "assigned_to_student": self.hidden_student.pk,
                "assigned_at": "2026-02-01",
                "returned_at": "",
                "status": AssetAssignment.ACTIVE,
                "note": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AssetAssignment.objects.filter(
                assigned_to_student=self.hidden_student,
                assigned_at=date(2026, 2, 1),
            ).exists()
        )

    def test_campus_admin_cannot_edit_other_campus_assignment_or_move_to_other_student(self):
        self.client.login(username="inventory_campus_admin", password="test-pass-123")

        hidden_edit_response = self.client.get(reverse("admin_inventory_assignments_edit", kwargs={"pk": self.hidden_assignment.pk}))
        self.hidden_assignment.delete()
        move_response = self.client.post(
            reverse("admin_inventory_assignments_edit", kwargs={"pk": self.assignment.pk}),
            {
                "item": self.item.pk,
                "quantity": "1",
                "assigned_to_user": "",
                "assigned_to_student": self.hidden_student.pk,
                "assigned_at": "2026-01-01",
                "returned_at": "",
                "status": AssetAssignment.ACTIVE,
                "note": "",
            },
        )

        self.assertEqual(hidden_edit_response.status_code, 404)
        self.assertEqual(move_response.status_code, 200)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.assigned_to_student, self.student)


class InventoryBalanceSnapshotTests(TestCase):
    def setUp(self):
        self.item = InventoryItem.objects.create(name="Router", sku="RTR-1", unit="pcs")

    def balance(self):
        self.item.refresh_from_db()
        return self.item.stock_on_hand()

    def test_movement_create_update_and_delete_keep_snapshot_in_sync(self):
        movement = StockMovement.objects.create(
            item=self.item, movement_type=StockMovement.IN, quantity=Decimal("10")
        )
        self.assertEqual(self.balance(), Decimal("10"))

        movement.quantity = Decimal("7")
        movement.save()
        self.assertEqual(self.balance(), Decimal("7"))

        movement.movement_type = StockMovement.OUT
        with self.assertRaises(ValidationError):
            movement.save()
        self.assertEqual(self.balance(), Decimal("7"))

        movement.refresh_from_db()
        movement.delete()
        self.assertEqual(self.balance(), Decimal("0"))

    def test_direct_stock_out_cannot_make_balance_negative(self):
        with self.assertRaises(ValidationError):
            StockMovement.objects.create(
                item=self.item,
                movement_type=StockMovement.OUT,
                quantity=Decimal("1"),
            )
        self.assertFalse(StockMovement.objects.exists())
        self.assertEqual(self.balance(), Decimal("0"))

    def test_reconciliation_command_detects_and_repairs_drift(self):
        StockMovement.objects.create(
            item=self.item, movement_type=StockMovement.IN, quantity=Decimal("4")
        )
        InventoryItem.objects.filter(pk=self.item.pk).update(cached_stock_on_hand=Decimal("99"))

        with self.assertRaisesMessage(Exception, "inventory balance mismatch"):
            call_command("reconcile_inventory_balances", stdout=StringIO())

        call_command("reconcile_inventory_balances", fix=True, stdout=StringIO())
        self.assertEqual(self.balance(), Decimal("4"))
