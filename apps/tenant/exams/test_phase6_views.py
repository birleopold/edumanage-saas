from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    Enrollment,
    Level,
    Program,
    Stream,
)
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, UserRole

from .external_models import (
    ExternalCandidate,
    ExternalCandidateSubject,
    ExternalExamBoard,
    ExternalExamCentre,
    ExternalExamResult,
    ExternalExamSession,
    ExternalExamSubject,
    ExternalResultImportBatch,
)


class Phase6ExternalExaminationViewTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Phase 6 View School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.year = AcademicYear.objects.create(name="2030")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.level = Level.objects.create(name="Senior Four", order=4)
        self.program = Program.objects.create(name="Ordinary Secondary", code="O-LVL")
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior Four",
            code="S4",
            level=self.level,
            program=self.program,
        )
        self.stream = Stream.objects.create(class_group=self.class_group, name="A")
        self.course = Course.objects.create(
            name="Mathematics",
            code="MATH",
            level=self.level,
            program=self.program,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="P6-VIEW-1",
            first_name="Peter",
            last_name="Candidate",
        )
        self.board = ExternalExamBoard.objects.create(code="UNEB", name="National Board")
        self.centre = ExternalExamCentre.objects.create(
            board=self.board,
            campus=self.campus,
            code="C001",
            name="Main Centre",
        )
        self.session = ExternalExamSession.objects.create(
            board=self.board,
            centre=self.centre,
            code="UCE-2030",
            name="Certificate Session 2030",
            academic_year=self.year,
            campus=self.campus,
            level=self.level,
            program=self.program,
            status=ExternalExamSession.REGISTRATION_OPEN,
            candidate_prefix="UCE-",
        )
        self.subject = ExternalExamSubject.objects.create(
            session=self.session,
            course=self.course,
            subject_code="456",
            max_score=100,
            is_compulsory=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="phase6admin",
            email="phase6@example.com",
            password="test-password",
        )
        self.client.force_login(self.superuser)

    def test_dashboard_is_available_to_full_administrator(self):
        response = self.client.get(reverse("admin_external_exam_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Candidate and external examination management")

    def test_create_board_normalizes_code(self):
        response = self.client.post(
            reverse("admin_external_exam_board_create"),
            {
                "code": " cambridge international ",
                "name": "Cambridge International",
                "board_type": ExternalExamBoard.INTERNATIONAL,
                "country_code": "gb",
                "candidate_number_label": "Candidate number",
                "subject_code_label": "Syllabus code",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ExternalExamBoard.objects.filter(code="CAMBRIDGE-INTERNATIONAL").exists())

    def test_bulk_registration_creates_candidate_and_no_enrollment(self):
        response = self.client.post(
            reverse("admin_external_exam_candidates", kwargs={"pk": self.session.pk}),
            {"action": "register_candidates"},
        )

        self.assertEqual(response.status_code, 302)
        candidate = ExternalCandidate.objects.get(session=self.session, student=self.student)
        self.assertTrue(candidate.candidate_number.startswith("UCE-"))
        self.assertEqual(Enrollment.objects.count(), 0)

    def test_compulsory_subject_action_is_idempotent(self):
        self.client.post(
            reverse("admin_external_exam_candidates", kwargs={"pk": self.session.pk}),
            {"action": "register_candidates"},
        )
        url = reverse("admin_external_exam_candidates", kwargs={"pk": self.session.pk})
        first = self.client.post(url, {"action": "register_compulsory_subjects"})
        second = self.client.post(url, {"action": "register_compulsory_subjects"})

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(ExternalCandidateSubject.objects.count(), 1)

    def test_candidate_export_returns_board_submission_csv(self):
        candidate = ExternalCandidate.objects.create(
            session=self.session,
            student=self.student,
            centre=self.centre,
            candidate_number="UCE-0001",
        )
        ExternalCandidateSubject.objects.create(candidate=candidate, subject=self.subject)

        response = self.client.get(
            reverse("admin_external_exam_export_candidates", kwargs={"pk": self.session.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("UCE-0001", response.content.decode())
        self.assertIn(self.subject.subject_code, response.content.decode())

    def test_result_import_defaults_to_dry_run(self):
        candidate = ExternalCandidate.objects.create(
            session=self.session,
            student=self.student,
            centre=self.centre,
            candidate_number="UCE-0001",
        )
        ExternalCandidateSubject.objects.create(candidate=candidate, subject=self.subject)
        csv_file = SimpleUploadedFile(
            "results.csv",
            b"candidate_number,subject_code,score,percentage,grade,result_status\nUCE-0001,456,75,75,A,PASS\n",
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("admin_external_exam_import_results", kwargs={"pk": self.session.pk}),
            {"csv_file": csv_file, "dry_run": "on"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ExternalExamResult.objects.count(), 0)
        self.assertEqual(ExternalResultImportBatch.objects.filter(dry_run=True).count(), 1)
        self.assertContains(response, "Dry-run summary")

    def test_campus_administrator_cannot_manage_external_board_configuration(self):
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        user = get_user_model().objects.create_user(
            username="phase6campusadmin",
            password="test-password",
        )
        UserRole.objects.create(user=user, role=role, campus=self.campus)
        self.client.force_login(user)

        response = self.client.get(reverse("admin_external_exam_dashboard"))

        self.assertEqual(response.status_code, 403)
