from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.users.models import Role, User

from .models import StaffProfile
from .payroll_models import Payslip


class StaffPayslipContinuityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = OrganizationProfile.objects.create(name="Payroll Continuity School")
        cls.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        cls.roles = {
            code: Role.objects.get_or_create(code=code, defaults={"name": label})[0]
            for code, label in Role.CODE_CHOICES
        }
        cls.users = {}
        for code in (Role.TEACHER, Role.PRINCIPAL, Role.ADMIN):
            user = User.objects.create_user(
                username=f"{code.lower()}-staff",
                password="StrongPass123!",
            )
            user.roles.add(cls.roles[code])
            staff = StaffProfile.objects.create(
                user=user,
                campus=cls.campus,
                staff_id=f"ST-{code}",
                first_name=code.title(),
                last_name="Staff",
            )
            cls.users[code] = (user, staff)

        cls.teacher_payslip = Payslip.objects.create(
            staff=cls.users[Role.TEACHER][1],
            period_year=2026,
            period_month=7,
            base_salary=Decimal("1000000.00"),
            gross_salary=Decimal("1000000.00"),
            net_salary=Decimal("1000000.00"),
        )

    def test_each_supported_role_keeps_its_own_shell(self):
        expected = {
            Role.TEACHER: "portals/teacher/base.html",
            Role.PRINCIPAL: "portals/admin/base.html",
            Role.ADMIN: "portals/admin/base.html",
        }
        for code, template in expected.items():
            with self.subTest(role=code):
                self.client.force_login(self.users[code][0])
                response = self.client.get(reverse("staff_payslips_list"))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)
                self.client.logout()

    def test_payslip_detail_remains_owner_scoped(self):
        self.client.force_login(self.users[Role.PRINCIPAL][0])
        response = self.client.get(
            reverse("staff_payslip_detail", kwargs={"pk": self.teacher_payslip.pk})
        )
        self.assertEqual(response.status_code, 404)
