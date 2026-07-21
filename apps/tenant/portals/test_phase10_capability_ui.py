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


class PortalToolDirectoryTests(TestCase):
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

    def test_full_administrator_sees_searchable_school_tools_without_phase_wording(self):
        user = get_user_model().objects.create_superuser(
            username="toolsadmin",
            email="toolsadmin@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All tools")
        self.assertContains(response, "Search tools")
        self.assertContains(response, "Teaching &amp; learning")
        self.assertContains(response, reverse("admin_education_framework_dashboard"))
        self.assertContains(response, reverse("admin_finance_clearance_dashboard"))
        self.assertContains(response, reverse("admin_external_exam_dashboard"))
        self.assertNotContains(response, "Phase 1")
        self.assertNotContains(response, "modernisation")
        self.assertNotContains(response, "rollout hardening")

    def test_campus_administrator_gets_operational_tools_only(self):
        user = self._role_user(Role.CAMPUS_ADMIN, "toolscampus")
        self.client.force_login(user)

        response = self.client.get(reverse("admin_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Campus tools")
        self.assertContains(response, reverse("admin_coursework_dashboard"))
        self.assertContains(response, reverse("admin_activity_sessions"))
        self.assertContains(response, reverse("admin_bed_allocations_list"))
        self.assertNotContains(response, reverse("admin_education_framework_dashboard"))
        self.assertNotContains(response, reverse("admin_finance_clearance_dashboard"))
        self.assertNotContains(response, reverse("admin_external_exam_dashboard"))
        self.assertNotContains(response, reverse("admin_users_list"))

    def test_teacher_sees_daily_teaching_and_support_tools(self):
        user = self._role_user(Role.TEACHER, "toolsteacher")
        TeacherProfile.objects.create(
            user=user,
            campus=self.campus,
            staff_id="TOOLS-T",
            first_name="Amina",
            last_name="Teacher",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("teacher_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teaching tools")
        self.assertContains(response, reverse("teacher_timetable"))
        self.assertContains(response, reverse("teacher_attendance_home"))
        self.assertContains(response, reverse("teacher_coursework_home"))
        self.assertContains(response, reverse("teacher_assessments_home"))
        self.assertContains(response, reverse("teacher_exams_home"))
        self.assertContains(response, reverse("staff_payslips_list"))
        self.assertNotContains(response, reverse("admin_assessment_framework_dashboard"))
        self.assertNotContains(response, "Managed by the school")

    def test_student_sees_learning_school_life_and_account_tools(self):
        user = self._role_user(Role.STUDENT, "toolsstudent")
        StudentProfile.objects.create(
            user=user,
            campus=self.campus,
            student_id="TOOLS-S",
            first_name="Daniel",
            last_name="Learner",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("student_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My school")
        self.assertContains(response, reverse("student_coursework_home"))
        self.assertContains(response, reverse("student_results_home"))
        self.assertContains(response, reverse("student_exams_dashboard"))
        self.assertContains(response, reverse("student_hostel_home"))
        self.assertContains(response, reverse("student_invoices_list"))
        self.assertContains(response, reverse("student_library_catalog"))
        self.assertNotContains(response, reverse("admin_pathway_dashboard"))
        self.assertNotContains(response, "School setup")

    def test_parent_sees_child_learning_services_fees_and_account_tools(self):
        user = self._role_user(Role.PARENT, "toolsparent")
        ParentProfile.objects.create(
            user=user,
            first_name="Grace",
            last_name="Guardian",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("parent_capabilities_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My children")
        self.assertContains(response, reverse("parent_coursework_home"))
        self.assertContains(response, reverse("parent_results_home"))
        self.assertContains(response, reverse("parent_exam_results"))
        self.assertContains(response, reverse("parent_hostel_home"))
        self.assertContains(response, reverse("parent_invoices_list"))
        self.assertContains(response, reverse("parent_communication_preferences"))
        self.assertNotContains(response, reverse("admin_finance_clearance_dashboard"))
        self.assertNotContains(response, "Managed by the school")

    def test_role_permissions_reject_cross_portal_tool_pages(self):
        teacher = self._role_user(Role.TEACHER, "toolscross")
        self.client.force_login(teacher)

        self.assertEqual(self.client.get(reverse("admin_capabilities_home")).status_code, 403)
        self.assertEqual(self.client.get(reverse("student_capabilities_home")).status_code, 403)
        self.assertEqual(self.client.get(reverse("parent_capabilities_home")).status_code, 403)

    def test_directory_contains_only_resolved_actionable_tools(self):
        user = get_user_model().objects.create_superuser(
            username="toolscatalog",
            email="toolscatalog@example.com",
            password="test-password",
        )

        context = build_capability_context(user, role="admin")

        self.assertGreaterEqual(len(context["capability_groups"]), 4)
        self.assertGreaterEqual(context["capability_tool_count"], 20)
        self.assertGreaterEqual(context["capability_action_count"], context["capability_tool_count"])
        for group in context["capability_groups"]:
            self.assertTrue(group["tools"])
            for tool in group["tools"]:
                self.assertTrue(tool["actions"])
                self.assertNotIn("phase", tool["title"].lower())
                for action in tool["actions"]:
                    self.assertTrue(action["url"].startswith("/"))
