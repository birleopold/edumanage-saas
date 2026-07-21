from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, UserRole

from .capability_catalog import build_capability_context


class Phase10CapabilityUiTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        if not self.campus:
            self.campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                is_default=True,
                is_active=True,
            )

    def _role_user(self, code: str, username: str):
        role, _ = Role.objects.get_or_create(code=code, defaults={"name": code.replace("_", " ").title()})
        user = get_user_model().objects.create_user(username=username, password="test-password")
        UserRole.objects.create(user=user, role=role, campus=self.campus if code == Role.CAMPUS_ADMIN else None)
        return user

    def test_full_administrator_sees_all_phase_configuration_entry_points(self):
        user = get_user_model().objects.create_superuser(
            username="phase10admin",
            email="phase10admin@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your integrated feature centre")
        self.assertContains(response, "Phase 9")
        self.assertContains(response, reverse("admin_education_framework_dashboard"))
        self.assertContains(response, reverse("admin_finance_clearance_dashboard"))
        self.assertContains(response, reverse("admin_external_exam_dashboard"))

    def test_campus_administrator_gets_operations_but_not_full_configuration_links(self):
        user = self._role_user(Role.CAMPUS_ADMIN, "phase10campus")
        self.client.force_login(user)

        response = self.client.get(reverse("admin_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Campus-scoped access is preserved")
        self.assertContains(response, reverse("admin_coursework_dashboard"))
        self.assertContains(response, reverse("admin_activity_sessions"))
        self.assertNotContains(response, reverse("admin_education_framework_dashboard"))
        self.assertNotContains(response, reverse("admin_finance_clearance_dashboard"))
        self.assertNotContains(response, reverse("admin_external_exam_dashboard"))

    def test_teacher_sees_teaching_assessment_and_exam_workflows_only(self):
        user = self._role_user(Role.TEACHER, "phase10teacher")
        TeacherProfile.objects.create(
            user=user,
            campus=self.campus,
            staff_id="P10-T",
            first_name="Amina",
            last_name="Teacher",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("teacher_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("teacher_coursework_home"))
        self.assertContains(response, reverse("teacher_assessments_home"))
        self.assertContains(response, reverse("teacher_exams_home"))
        self.assertNotContains(response, reverse("admin_assessment_framework_dashboard"))

    def test_student_sees_learning_results_exam_boarding_and_finance_workflows(self):
        user = self._role_user(Role.STUDENT, "phase10student")
        StudentProfile.objects.create(
            user=user,
            campus=self.campus,
            student_id="P10-S",
            first_name="Daniel",
            last_name="Learner",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("student_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("student_coursework_home"))
        self.assertContains(response, reverse("student_results_home"))
        self.assertContains(response, reverse("student_exams_dashboard"))
        self.assertContains(response, reverse("student_hostel_home"))
        self.assertContains(response, reverse("student_invoices_list"))
        self.assertNotContains(response, reverse("admin_pathway_dashboard"))

    def test_parent_sees_child_facing_learning_exam_boarding_and_finance_workflows(self):
        user = self._role_user(Role.PARENT, "phase10parent")
        ParentProfile.objects.create(
            user=user,
            first_name="Grace",
            last_name="Guardian",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("parent_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("parent_coursework_home"))
        self.assertContains(response, reverse("parent_results_home"))
        self.assertContains(response, reverse("parent_exam_results"))
        self.assertContains(response, reverse("parent_hostel_home"))
        self.assertContains(response, reverse("parent_invoices_list"))
        self.assertNotContains(response, reverse("admin_finance_clearance_dashboard"))

    def test_role_permissions_reject_cross_portal_capability_pages(self):
        teacher = self._role_user(Role.TEACHER, "phase10cross")
        self.client.force_login(teacher)

        self.assertEqual(self.client.get(reverse("admin_capabilities_home")).status_code, 403)
        self.assertEqual(self.client.get(reverse("student_capabilities_home")).status_code, 403)
        self.assertEqual(self.client.get(reverse("parent_capabilities_home")).status_code, 403)

    def test_catalog_has_exactly_nine_completed_phases_and_valid_actions(self):
        user = get_user_model().objects.create_superuser(
            username="phase10catalog",
            email="phase10catalog@example.com",
            password="test-password",
        )

        context = build_capability_context(user, role="admin")

        self.assertEqual(len(context["capability_phases"]), 9)
        self.assertEqual([row["number"] for row in context["capability_phases"]], list(range(1, 10)))
        self.assertGreaterEqual(context["capability_action_count"], 9)
        for phase in context["capability_phases"]:
            for action in phase["actions"]:
                self.assertTrue(action["url"].startswith("/"))
