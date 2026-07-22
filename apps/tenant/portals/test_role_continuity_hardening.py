from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role, User

from .campus_permissions import enforce_campus_scope
from .permissions import admin_portal_required, role_required
from .role_navigation import portal_home_url_for
from .views import landing_page


class RoleContinuityHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = OrganizationProfile.objects.create(name="Role Continuity School")
        cls.campus_one = Campus.objects.create(
            organization=cls.organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        cls.campus_two = Campus.objects.create(
            organization=cls.organization,
            name="Annex Campus",
            code="ANNEX",
        )
        cls.roles = {
            code: Role.objects.get_or_create(code=code, defaults={"name": label})[0]
            for code, label in Role.CODE_CHOICES
        }
        cls.principal = User.objects.create_user(username="principal", password="StrongPass123!")
        cls.principal.roles.add(cls.roles[Role.PRINCIPAL])
        cls.teacher = User.objects.create_user(username="teacher-role", password="StrongPass123!")
        cls.teacher.roles.add(cls.roles[Role.TEACHER])

    def setUp(self):
        self.factory = RequestFactory()

    def test_principal_shell_home_and_admin_guard_are_consistent(self):
        self.assertEqual(base_template_for(self.principal), "portals/admin/base.html")
        self.assertEqual(portal_home_url_for(self.principal), reverse("admin_home"))

        request = self.factory.get("/")
        request.user = self.principal
        response = landing_page(request)
        self.assertRedirects(response, reverse("admin_home"), fetch_redirect_response=False)

        @admin_portal_required
        def protected(_request):
            return HttpResponse("ok")

        response = protected(request)
        self.assertEqual(response.status_code, 200)

    def test_principal_is_tenant_wide_for_campus_scoping(self):
        visible = enforce_campus_scope(Campus.objects.order_by("pk"), self.principal)
        self.assertEqual(list(visible), [self.campus_one, self.campus_two])

    def test_role_required_defensively_accepts_legacy_iterables(self):
        @role_required([Role.TEACHER, Role.PRINCIPAL])
        def protected(_request):
            return HttpResponse("ok")

        request = self.factory.get("/staff/payslips/")
        request.user = self.teacher
        response = protected(request)
        self.assertEqual(response.status_code, 200)
