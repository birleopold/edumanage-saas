from django.test import TestCase

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    ClassGroupPathwayAssignment,
    Course,
    CourseOffering,
    Enrollment,
    Level,
    Program,
    ProgrammePathway,
    ProgrammePathwayLevel,
    Stream,
    SubjectCombination,
    SubjectCombinationCourse,
)
from .pathway_services import (
    bootstrap_programme_pathways,
    create_missing_offerings,
    offering_plan,
    pathway_framework_readiness,
    resolve_class_group_pathway,
    resolve_student_pathway,
)


class Phase5ProgrammePathwayTests(TestCase):
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
        self.year = AcademicYear.objects.create(name="2027")
        self.term_one = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.term_two = AcademicTerm.objects.create(year=self.year, name="Term 2", order=2)
        self.level = Level.objects.create(name="Senior Five", order=5)
        self.program = Program.objects.create(name="Advanced Secondary", code="A-LVL")
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior Five",
            code="S5",
            level=self.level,
            program=self.program,
        )
        self.stream = Stream.objects.create(class_group=self.class_group, name="A")
        self.physics = Course.objects.create(
            name="Physics",
            code="PHY",
            level=self.level,
            program=self.program,
        )
        self.chemistry = Course.objects.create(
            name="Chemistry",
            code="CHEM",
            level=self.level,
            program=self.program,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="P5-001",
            first_name="Amina",
            last_name="Learner",
        )

    def _configured_pathway(self, code="PCM", priority=0):
        pathway = ProgrammePathway.objects.create(
            code=f"PATH-{code}",
            name=f"{code} Pathway",
            program=self.program,
            campus=self.campus,
            priority=priority,
            is_default=priority == 0,
            is_active=True,
        )
        ProgrammePathwayLevel.objects.create(
            pathway=pathway,
            level=self.level,
            sequence=1,
            is_entry=True,
            is_exit=True,
            is_active=True,
        )
        combination = SubjectCombination.objects.create(
            code=f"COMB-{code}",
            name=f"{code} Combination",
            pathway=pathway,
            level=self.level,
            minimum_subjects=2,
            maximum_subjects=2,
            priority=priority,
            is_default=True,
            is_active=True,
        )
        SubjectCombinationCourse.objects.create(
            combination=combination,
            course=self.physics,
            role=SubjectCombinationCourse.CORE,
            order=1,
        )
        SubjectCombinationCourse.objects.create(
            combination=combination,
            course=self.chemistry,
            role=SubjectCombinationCourse.CORE,
            order=2,
        )
        return pathway, combination

    def test_exact_term_assignment_wins_over_standing_assignment(self):
        standing_pathway, standing_combination = self._configured_pathway("GENERAL", priority=0)
        term_pathway, term_combination = self._configured_pathway("TERM", priority=10)
        ClassGroupPathwayAssignment.objects.create(
            class_group=self.class_group,
            pathway=standing_pathway,
            subject_combination=standing_combination,
            is_active=True,
        )
        exact = ClassGroupPathwayAssignment.objects.create(
            class_group=self.class_group,
            pathway=term_pathway,
            subject_combination=term_combination,
            academic_term=self.term_one,
            is_active=True,
        )

        resolution = resolve_class_group_pathway(self.class_group, self.term_one)
        standing_resolution = resolve_class_group_pathway(self.class_group, self.term_two)

        self.assertEqual(resolution.assignment, exact)
        self.assertEqual(resolution.pathway, term_pathway)
        self.assertEqual(resolution.combination, term_combination)
        self.assertEqual(standing_resolution.pathway, standing_pathway)

    def test_student_resolution_uses_current_stream_and_class_group(self):
        pathway, combination = self._configured_pathway()
        assignment = ClassGroupPathwayAssignment.objects.create(
            class_group=self.class_group,
            pathway=pathway,
            subject_combination=combination,
            is_active=True,
        )

        resolution = resolve_student_pathway(self.student, self.term_one)

        self.assertEqual(resolution.assignment, assignment)
        self.assertEqual(resolution.pathway, pathway)
        self.assertEqual(resolution.combination, combination)

    def test_offering_creation_adds_only_missing_records_and_never_enrolls(self):
        pathway, combination = self._configured_pathway()
        ClassGroupPathwayAssignment.objects.create(
            class_group=self.class_group,
            pathway=pathway,
            subject_combination=combination,
            is_active=True,
        )
        existing = CourseOffering.objects.create(
            campus=self.campus,
            class_group=self.class_group,
            course=self.physics,
            term=self.term_one,
        )

        preview = offering_plan(self.class_group, self.term_one)
        first = create_missing_offerings(self.class_group, self.term_one)
        second = create_missing_offerings(self.class_group, self.term_one)

        self.assertEqual(preview["existing_count"], 1)
        self.assertEqual(preview["missing_count"], 1)
        self.assertEqual(first["created_count"], 1)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(CourseOffering.objects.filter(class_group=self.class_group, term=self.term_one).count(), 2)
        self.assertTrue(CourseOffering.objects.filter(pk=existing.pk).exists())
        self.assertEqual(Enrollment.objects.count(), 0)

    def test_bootstrap_reuses_existing_links_without_assigning_classes(self):
        dry_run = bootstrap_programme_pathways(dry_run=True)

        self.assertEqual(dry_run["pathways_created"], 1)
        self.assertEqual(ProgrammePathway.objects.count(), 0)
        self.assertEqual(ClassGroupPathwayAssignment.objects.count(), 0)

        summary = bootstrap_programme_pathways(dry_run=False)

        pathway = ProgrammePathway.objects.get(code="PATH-A-LVL")
        combination = SubjectCombination.objects.get(code="COMB-A-LVL")
        self.assertEqual(summary["pathways_created"], 1)
        self.assertEqual(pathway.program, self.program)
        self.assertEqual(pathway.pathway_levels.count(), 1)
        self.assertEqual(combination.course_memberships.count(), 2)
        self.assertEqual(ClassGroupPathwayAssignment.objects.count(), 0)
        self.assertEqual(CourseOffering.objects.count(), 0)
        self.assertEqual(Enrollment.objects.count(), 0)

    def test_missing_configuration_leaves_current_operations_unchanged(self):
        offering = CourseOffering.objects.create(
            campus=self.campus,
            class_group=self.class_group,
            course=self.physics,
            term=self.term_one,
        )

        resolution = resolve_class_group_pathway(self.class_group, self.term_one)
        plan = offering_plan(self.class_group, self.term_one)

        self.assertIsNone(resolution.pathway)
        self.assertEqual(plan["rows"], [])
        self.assertTrue(CourseOffering.objects.filter(pk=offering.pk).exists())

    def test_readiness_accepts_complete_configuration(self):
        pathway, combination = self._configured_pathway()
        ClassGroupPathwayAssignment.objects.create(
            class_group=self.class_group,
            pathway=pathway,
            subject_combination=combination,
            is_active=True,
        )

        readiness = pathway_framework_readiness()

        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["invalid_pathway_count"], 0)
        self.assertEqual(readiness["invalid_combination_count"], 0)
        self.assertEqual(readiness["invalid_assignment_count"], 0)
        self.assertEqual(readiness["unassigned_class_group_count"], 0)
