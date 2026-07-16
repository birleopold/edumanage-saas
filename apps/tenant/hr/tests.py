from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import Role, User, UserRole

from .models import Department, Position, StaffProfile
from .payroll_models import PayGrade, Payslip, PayrollApproval, SalaryStructure


class HrAdminCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other HR Campus",
            is_active=True,
        )
        self.department = Department.objects.create(
            campus=self.campus,
            name="Visible HR Department",
            code="VIS-HR",
            is_active=True,
        )
        self.other_department = Department.objects.create(
            campus=self.other_campus,
            name="Hidden HR Department",
            code="HID-HR",
            is_active=True,
        )
        self.shared_department = Department.objects.create(
            campus=None,
            name="Shared HR Department",
            code="SHR-HR",
            is_active=True,
        )
        self.position = Position.objects.create(
            department=self.department,
            title="Visible HR Position",
            is_active=True,
        )
        self.other_position = Position.objects.create(
            department=self.other_department,
            title="Hidden HR Position",
            is_active=True,
        )
        self.staff = StaffProfile.objects.create(
            first_name="Visible",
            last_name="Staff",
            staff_id="HR-VISIBLE",
            campus=self.campus,
            department=self.department,
            position=self.position,
        )
        self.hidden_staff = StaffProfile.objects.create(
            first_name="Hidden",
            last_name="Staff",
            staff_id="HR-HIDDEN",
            campus=self.other_campus,
            department=self.other_department,
            position=self.other_position,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="hr_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_staff_list_ignores_forged_campus_filter(self):
        self.client.login(username="hr_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_hr_staff_list"), {"campus": self.other_campus.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HR-VISIBLE")
        self.assertNotContains(response, "HR-HIDDEN")
        self.assertEqual(response.context["selected_campus_id"], self.campus.pk)

    def test_campus_admin_cannot_access_other_campus_staff(self):
        self.client.login(username="hr_campus_admin", password="test-pass-123")

        detail_response = self.client.get(reverse("admin_hr_staff_detail", kwargs={"pk": self.hidden_staff.pk}))
        edit_response = self.client.get(reverse("admin_hr_staff_edit", kwargs={"pk": self.hidden_staff.pk}))

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(edit_response.status_code, 404)

    def test_campus_admin_cannot_create_or_move_staff_to_other_campus(self):
        self.client.login(username="hr_campus_admin", password="test-pass-123")

        create_response = self.client.post(
            reverse("admin_hr_staff_create"),
            {
                "campus": self.other_campus.pk,
                "staff_id": "HR-FORGED",
                "first_name": "Forged",
                "last_name": "Staff",
                "phone": "",
                "email": "",
                "staff_category": StaffProfile.TEACHING,
                "department": self.department.pk,
                "position": self.position.pk,
                "reports_to": "",
                "is_active": "on",
            },
        )
        edit_response = self.client.post(
            reverse("admin_hr_staff_edit", kwargs={"pk": self.staff.pk}),
            {
                "campus": self.other_campus.pk,
                "staff_id": self.staff.staff_id,
                "first_name": self.staff.first_name,
                "last_name": self.staff.last_name,
                "phone": "",
                "email": "",
                "staff_category": self.staff.staff_category,
                "department": self.department.pk,
                "position": self.position.pk,
                "reports_to": "",
                "is_active": "on",
            },
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 200)
        self.assertFalse(StaffProfile.objects.filter(staff_id="HR-FORGED").exists())
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.campus, self.campus)

    def test_campus_admin_departments_and_positions_are_scoped(self):
        self.client.login(username="hr_campus_admin", password="test-pass-123")

        departments_response = self.client.get(reverse("admin_hr_departments_list"))
        positions_response = self.client.get(reverse("admin_hr_positions_list"))
        hidden_department_edit = self.client.get(reverse("admin_hr_department_edit", kwargs={"pk": self.other_department.pk}))
        hidden_position_edit = self.client.get(reverse("admin_hr_position_edit", kwargs={"pk": self.other_position.pk}))

        self.assertEqual(departments_response.status_code, 200)
        self.assertContains(departments_response, "Visible HR Department")
        self.assertContains(departments_response, "Shared HR Department")
        self.assertNotContains(departments_response, "Hidden HR Department")
        self.assertEqual(positions_response.status_code, 200)
        self.assertContains(positions_response, "Visible HR Position")
        self.assertNotContains(positions_response, "Hidden HR Position")
        self.assertEqual(hidden_department_edit.status_code, 404)
        self.assertEqual(hidden_position_edit.status_code, 404)

    def test_campus_admin_cannot_create_position_for_other_campus_department(self):
        self.client.login(username="hr_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_hr_position_create"),
            {
                "department": self.other_department.pk,
                "title": "Forged HR Position",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Position.objects.filter(title="Forged HR Position").exists())


class PayrollCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Payroll Campus",
            is_active=True,
        )
        self.staff = StaffProfile.objects.create(
            first_name="Visible",
            last_name="Payroll",
            staff_id="PAY-VISIBLE",
            campus=self.campus,
        )
        self.hidden_staff = StaffProfile.objects.create(
            first_name="Hidden",
            last_name="Payroll",
            staff_id="PAY-HIDDEN",
            campus=self.other_campus,
        )
        self.pay_grade = PayGrade.objects.create(
            name="Payroll Grade",
            code="PAY-G",
            min_salary=Decimal("1000"),
            max_salary=Decimal("5000"),
            is_active=True,
        )
        self.salary = SalaryStructure.objects.create(
            staff=self.staff,
            pay_grade=self.pay_grade,
            base_salary=Decimal("1500"),
            effective_date=date(2026, 1, 1),
            is_active=True,
        )
        self.hidden_salary = SalaryStructure.objects.create(
            staff=self.hidden_staff,
            pay_grade=self.pay_grade,
            base_salary=Decimal("2500"),
            effective_date=date(2026, 1, 1),
            is_active=True,
        )
        self.payslip = Payslip.objects.create(
            staff=self.staff,
            period_year=2026,
            period_month=7,
            base_salary=Decimal("1500"),
            gross_salary=Decimal("1500"),
            net_salary=Decimal("1500"),
            status=Payslip.PENDING_APPROVAL,
        )
        self.hidden_payslip = Payslip.objects.create(
            staff=self.hidden_staff,
            period_year=2026,
            period_month=7,
            base_salary=Decimal("2500"),
            gross_salary=Decimal("2500"),
            net_salary=Decimal("2500"),
            status=Payslip.PENDING_APPROVAL,
        )
        self.approval = PayrollApproval.objects.create(
            payslip=self.payslip,
            approver_role=Role.CAMPUS_ADMIN,
            status=PayrollApproval.PENDING,
        )
        self.hidden_approval = PayrollApproval.objects.create(
            payslip=self.hidden_payslip,
            approver_role=Role.CAMPUS_ADMIN,
            status=PayrollApproval.PENDING,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="payroll_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_salary_structures_are_scoped(self):
        self.client.login(username="payroll_campus_admin", password="test-pass-123")

        list_response = self.client.get(reverse("admin_hr_payroll_salary_structures_list"))
        hidden_edit_response = self.client.get(reverse("admin_hr_payroll_salary_structure_edit", kwargs={"pk": self.hidden_salary.pk}))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "PAY-VISIBLE")
        self.assertNotContains(list_response, "PAY-HIDDEN")
        self.assertEqual(hidden_edit_response.status_code, 404)

    def test_campus_admin_cannot_create_salary_structure_for_other_campus_staff(self):
        self.hidden_salary.delete()
        self.client.login(username="payroll_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_hr_payroll_salary_structure_create"),
            {
                "staff": self.hidden_staff.pk,
                "pay_grade": self.pay_grade.pk,
                "base_salary": "2500",
                "effective_date": "2026-01-01",
                "end_date": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SalaryStructure.objects.filter(staff=self.hidden_staff).exists())

    def test_campus_admin_payslips_and_pdf_are_scoped(self):
        self.client.login(username="payroll_campus_admin", password="test-pass-123")

        list_response = self.client.get(reverse("admin_hr_payroll_payslips_list"))
        hidden_detail_response = self.client.get(reverse("admin_hr_payroll_payslip_detail", kwargs={"pk": self.hidden_payslip.pk}))
        hidden_pdf_response = self.client.get(reverse("admin_hr_payroll_payslip_pdf", kwargs={"pk": self.hidden_payslip.pk}))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "PAY-VISIBLE")
        self.assertNotContains(list_response, "PAY-HIDDEN")
        self.assertEqual(hidden_detail_response.status_code, 404)
        self.assertEqual(hidden_pdf_response.status_code, 404)

    def test_campus_admin_payslip_generate_uses_scoped_staff(self):
        self.payslip.delete()
        self.hidden_payslip.delete()
        self.client.login(username="payroll_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_hr_payroll_payslip_generate"),
            {
                "period_year": "2026",
                "period_month": "8",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Payslip.objects.filter(staff=self.staff, period_year=2026, period_month=8).exists())
        self.assertFalse(Payslip.objects.filter(staff=self.hidden_staff, period_year=2026, period_month=8).exists())

    def test_campus_admin_approval_dashboard_and_action_are_scoped(self):
        self.client.login(username="payroll_campus_admin", password="test-pass-123")

        dashboard_response = self.client.get(reverse("admin_hr_payroll_approval_dashboard"))
        hidden_detail_response = self.client.get(reverse("admin_hr_payroll_approval_detail", kwargs={"pk": self.hidden_approval.pk}))
        hidden_action_response = self.client.post(
            reverse("admin_hr_payroll_approval_action", kwargs={"pk": self.hidden_approval.pk}),
            {"action": "approve", "comments": ""},
        )

        self.assertEqual(dashboard_response.status_code, 200)
        approval_ids = {item.pk for item in dashboard_response.context["approvals"]}
        self.assertIn(self.approval.pk, approval_ids)
        self.assertNotIn(self.hidden_approval.pk, approval_ids)
        self.assertEqual(hidden_detail_response.status_code, 404)
        self.assertEqual(hidden_action_response.status_code, 404)
