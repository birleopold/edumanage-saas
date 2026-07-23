from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole

from .templatetags.registry_insights import registry_summary


class FusionWorkspaceRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = get_or_create_organization()
        cls.campus = Campus.objects.filter(organization=organization).first()
        if cls.campus is None:
            cls.campus = Campus.objects.create(
                organization=organization,
                name="Fusion Main Campus",
                code="FUSION",
                is_default=True,
                is_active=True,
            )

        admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin"})
        cls.admin = User.objects.create_user(
            username="fusion_admin",
            password="StrongPass123!",
            email="fusion-admin@example.com",
        )
        cls.admin.roles.add(admin_role)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_high_frequency_admin_workspaces_render_fused_interface(self):
        expectations = {
            "admin_students_list": "Every learner, clearly organised",
            "admin_students_create": 'data-guided-form="student"',
            "admin_teachers_list": "Faculty records built for daily work",
            "admin_teachers_create": 'data-guided-form="teacher"',
            "admin_finance_dashboard": "Finance attention queue",
            "admin_attendance_sessions_list": "Attendance that is easy to act on",
            "admin_timetable_grid": "A clear picture of every teaching period",
        }

        for route_name, marker in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, marker, html=False)

    def test_shared_fusion_assets_are_loaded_from_portal_shell(self):
        response = self.client.get(reverse("admin_students_list"))

        self.assertContains(response, "css/fusion-workflows.css")
        self.assertContains(response, "css/fusion-scheduling.css")
        self.assertContains(response, "js/fusion-workflows.js")


class RegistryInsightScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = get_or_create_organization()
        cls.campus = Campus.objects.filter(organization=organization).first()
        if cls.campus is None:
            cls.campus = Campus.objects.create(
                organization=organization,
                name="Registry Main Campus",
                code="REG-MAIN",
                is_default=True,
                is_active=True,
            )
        cls.other_campus = Campus.objects.create(
            organization=organization,
            name="Registry Other Campus",
            code="REG-OTHER",
            is_active=True,
        )

        campus_role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        cls.campus_admin = User.objects.create_user(
            username="fusion_campus_admin",
            password="StrongPass123!",
        )
        cls.campus_admin.roles.add(campus_role)
        UserRole.objects.create(user=cls.campus_admin, role=campus_role, campus=cls.campus)

        StudentProfile.objects.create(
            campus=cls.campus,
            student_id="REG-ST-1",
            first_name="Active",
            last_name="Learner",
            is_active=True,
        )
        StudentProfile.objects.create(
            campus=cls.other_campus,
            student_id="REG-ST-2",
            first_name="Other",
            last_name="Learner",
            is_active=True,
        )
        TeacherProfile.objects.create(
            campus=cls.campus,
            staff_id="REG-T-1",
            first_name="Campus",
            last_name="Teacher",
            email="",
            is_active=True,
        )
        TeacherProfile.objects.create(
            campus=cls.other_campus,
            staff_id="REG-T-2",
            first_name="Other",
            last_name="Teacher",
            email="other@example.com",
            is_active=True,
        )

    def setUp(self):
        self.factory = RequestFactory()

    def _context(self):
        request = self.factory.get("/admin/")
        request.user = self.campus_admin
        return {"request": request}

    def test_student_summary_remains_inside_campus_scope(self):
        summary = registry_summary(self._context(), "student", self.other_campus.pk)

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["active"], 1)
        self.assertEqual(summary["portal"], 0)
        self.assertEqual(summary["attention"], 1)

    def test_teacher_summary_remains_inside_campus_scope(self):
        summary = registry_summary(self._context(), "teacher", self.other_campus.pk)

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["active"], 1)
        self.assertEqual(summary["portal"], 0)
        self.assertEqual(summary["attention"], 1)
