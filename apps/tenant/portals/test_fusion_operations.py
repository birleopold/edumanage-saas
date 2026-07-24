from django.test import TestCase
from django.urls import reverse

from apps.tenant.admissions.models import Applicant
from apps.tenant.announcements.models import Announcement
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile
from apps.tenant.users.models import Role, User


class FusedOperationsWorkspaceTests(TestCase):
    """Render the fused administrator workspaces through their secured routes."""

    @classmethod
    def setUpTestData(cls):
        organization = get_or_create_organization()
        cls.campus = Campus.objects.filter(organization=organization).first()
        if cls.campus is None:
            cls.campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                is_active=True,
            )

        admin_role, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Administrator"},
        )
        cls.admin = User.objects.create_user(
            username="fusion-operations-admin",
            password="StrongPass123!",
            email="fusion-admin@example.test",
        )
        cls.admin.roles.add(admin_role)

        cls.applicant = Applicant.objects.create(
            campus=cls.campus,
            first_name="Amina",
            last_name="Fusion",
            phone="0700000099",
            status=Applicant.IN_REVIEW,
        )
        ParentProfile.objects.create(
            first_name="Grace",
            last_name="Guardian",
            phone="0710000099",
            is_active=True,
        )
        Announcement.objects.create(
            title="Term opening guidance",
            body="Learners should report by 8:00 a.m.",
            audience=Announcement.ALL,
            is_active=True,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def assert_workspace(self, route_name: str, expected_text: str):
        response = self.client.get(reverse(route_name))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expected_text)
        return response

    def test_admissions_register_and_pipeline_render_fused_workspaces(self):
        register_response = self.assert_workspace(
            "admin_admissions_applicants",
            "Move every applicant forward with confidence",
        )
        pipeline_response = self.assert_workspace(
            "admin_admissions_pipeline",
            "See where every application stands",
        )

        self.assertContains(register_response, self.applicant.application_reference)
        self.assertContains(pipeline_response, self.applicant.full_name())

    def test_applicant_review_workspace_renders_decision_evidence(self):
        response = self.client.get(
            reverse(
                "admin_admissions_applicant_detail",
                kwargs={"pk": self.applicant.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review evidence before conversion")
        self.assertContains(response, "Interviews and tests")
        self.assertContains(response, "Communication history")

    def test_family_and_communication_workspaces_render(self):
        self.assert_workspace(
            "admin_parents_list",
            "Keep every learner connected to the right guardian",
        )
        self.assert_workspace(
            "admin_announcements_list",
            "Publish clear messages to the right school audience",
        )

    def test_library_inventory_and_examination_workspaces_render(self):
        self.assert_workspace(
            "admin_library_books_list",
            "Keep books available, traceable and returned on time",
        )
        self.assert_workspace(
            "admin_inventory_dashboard",
            "Know what the school owns",
        )
        self.assert_workspace(
            "admin_exams_list",
            "Plan, supervise and publish examinations responsibly",
        )
        self.assert_workspace(
            "admin_exam_papers_list",
            "Build each paper from setup through scores",
        )

    def test_assessment_reporting_and_analytics_workspaces_render(self):
        expectations = {
            "admin_assessments_list": "Move from assessment setup to published results with confidence",
            "admin_assessment_framework_dashboard": "Define how school assessments are classified and combined",
            "admin_reports_overview": "Turn school records into decisions and accountable exports",
            "admin_analytics_dashboard": "See achievement, coverage and learner risk before intervention is late",
        }

        for route_name, marker in expectations.items():
            with self.subTest(route_name=route_name):
                self.assert_workspace(route_name, marker)

    def test_welfare_health_transport_and_boarding_workspaces_render(self):
        expectations = {
            "admin_incidents_list": "Respond consistently, fairly and with complete evidence",
            "admin_sickbay_dashboard": "Record care clearly and never lose a follow-up",
            "admin_sickbay_visit_list": "Find every visit, outcome and follow-up quickly",
            "admin_transport_vehicles_list": "Keep every route staffed, roadworthy and within capacity",
            "admin_boarding_welfare_dashboard": "Know where every boarder is and who needs support",
        }

        for route_name, marker in expectations.items():
            with self.subTest(route_name=route_name):
                self.assert_workspace(route_name, marker)

    def test_document_control_and_hr_workspaces_render(self):
        expectations = {
            "admin_documents_list": "Publish the right file to the right audience",
            "admin_hr_staff_list": "Keep every staff record complete, accountable and ready for work",
        }

        for route_name, marker in expectations.items():
            with self.subTest(route_name=route_name):
                self.assert_workspace(route_name, marker)

    def test_welfare_health_transport_and_hr_forms_render_supporting_guidance(self):
        expectations = {
            "admin_incidents_create": "Case-quality checklist",
            "admin_sickbay_visit_create": "Care-record checklist",
            "admin_transport_vehicle_create": "Fleet-readiness checklist",
            "admin_documents_upload": "Publishing checklist",
            "admin_hr_staff_create": "Staff-record checklist",
            "admin_assessments_create": "Assessment-quality checklist",
        }

        for route_name, marker in expectations.items():
            with self.subTest(route_name=route_name):
                self.assert_workspace(route_name, marker)

    def test_guided_operational_forms_render_progressive_enhancement_markers(self):
        expectations = {
            "admin_admissions_applicant_create": 'data-guided-form="applicant"',
            "admin_parents_create": 'data-guided-form="parent"',
            "admin_announcements_create": 'data-guided-form="announcement"',
            "admin_library_book_create": 'data-guided-form="book"',
            "admin_exams_create": 'data-guided-form="exam"',
        }

        for route_name, marker in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, marker, html=False)
