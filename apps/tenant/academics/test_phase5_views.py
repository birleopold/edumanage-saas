from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.users.models import Role, UserRole

from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    ClassGroupPathwayAssignment,
    Course,
    CourseOffering,
    Level,
    Program,
    ProgrammePathway,
    ProgrammePathwayLevel,
    SubjectCombination,
    SubjectCombinationCourse,
)


class Phase5PathwayViewTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Phase 5 View School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.program = Program.objects.create(name="Advanced Secondary", code="A-LVL")
        self.level = Level.objects.create(name="Senior Six", order=6)
        self.year = AcademicYear.objects.create(name="2028")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior Six",
            code="S6",
            program=self.program,
            level=self.level,
        )
        self.course = Course.objects.create(
            name="Biology",
            code="BIO",
            program=self.program,
            level=self.level,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="phase5admin",
            email="phase5@example.com",
            password="test-password",
        )
        self.client.force_login(self.superuser)

    def _configured_assignment(self):
        pathway = ProgrammePathway.objects.create(
            code="PATH-BCM",
            name="BCM Pathway",
            program=self.program,
            campus=self.campus,
            is_default=True,
            is_active=True,
        )
        ProgrammePathwayLevel.objects.create(
            pathway=pathway,
            level=self.level,
            sequence=1,
            is_entry=True,
            is_exit=True,
        )
        combination = SubjectCombination.objects.create(
            code="COMB-BCM",
            name="BCM",
            pathway=pathway,
            level=self.level,
            minimum_subjects=1,
            maximum_subjects=1,
            is_default=True,
            is_active=True,
        )
        SubjectCombinationCourse.objects.create(
            combination=combination,
            course=self.course,
            role=SubjectCombinationCourse.CORE,
            order=1,
        )
        ClassGroupPathwayAssignment.objects.create(
            class_group=self.class_group,
            pathway=pathway,
            subject_combination=combination,
            is_active=True,
        )
        return pathway, combination

    def test_dashboard_is_available_to_full_administrator(self):
        response = self.client.get(reverse("admin_pathway_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Programme pathways and subject combinations")

    def test_create_pathway_normalizes_code(self):
        response = self.client.post(
            reverse("admin_pathway_create"),
            {
                "code": " science route ",
                "name": "Science Route",
                "description": "",
                "program": self.program.pk,
                "campus": self.campus.pk,
                "priority": "10",
                "is_default": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProgrammePathway.objects.filter(code="SCIENCE-ROUTE").exists())

    def test_offering_creation_view_creates_only_missing_offering(self):
        self._configured_assignment()
        response = self.client.post(
            reverse("admin_pathway_offerings"),
            {
                "class_group": self.class_group.pk,
                "term": self.term.pk,
                "action": "create",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            CourseOffering.objects.filter(
                class_group=self.class_group,
                term=self.term,
                course=self.course,
            ).count(),
            1,
        )

    def test_campus_administrator_cannot_manage_institution_pathways(self):
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        user = get_user_model().objects.create_user(
            username="phase5campusadmin",
            password="test-password",
        )
        UserRole.objects.create(user=user, role=role, campus=self.campus)
        self.client.force_login(user)

        response = self.client.get(reverse("admin_pathway_dashboard"))

        self.assertEqual(response.status_code, 403)
