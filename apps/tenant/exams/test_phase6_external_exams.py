from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    Level,
    Program,
    Stream,
)
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

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
from .external_services import (
    candidate_export_csv,
    external_exam_readiness,
    import_external_results,
    register_compulsory_subjects,
    register_eligible_candidates,
)
from .models import Exam, ExamPaper, ExamScore


class Phase6ExternalExaminationTests(TestCase):
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
        self.year = AcademicYear.objects.create(name="2029")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.level = Level.objects.create(name="Senior Six", order=6)
        self.program = Program.objects.create(name="Advanced Secondary", code="A-LVL")
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior Six",
            code="S6",
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
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.physics,
            term=self.term,
            class_group=self.class_group,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="P6-001",
            learner_id="EMIS-001",
            first_name="Amina",
            last_name="Learner",
        )
        self.board = ExternalExamBoard.objects.create(
            code="uneb",
            name="National Examinations Board",
            country_code="ug",
        )
        self.centre = ExternalExamCentre.objects.create(
            board=self.board,
            campus=self.campus,
            code="centre 001",
            name="Main Centre",
        )
        self.session = ExternalExamSession.objects.create(
            board=self.board,
            centre=self.centre,
            code="uace 2029",
            name="Advanced Certificate 2029",
            academic_year=self.year,
            campus=self.campus,
            level=self.level,
            program=self.program,
            status=ExternalExamSession.REGISTRATION_OPEN,
            candidate_prefix="UACE-",
            candidate_number_padding=4,
        )
        self.physics_subject = ExternalExamSubject.objects.create(
            session=self.session,
            course=self.physics,
            subject_code="p510",
            max_score=100,
            is_compulsory=True,
            order=1,
        )
        self.chemistry_subject = ExternalExamSubject.objects.create(
            session=self.session,
            course=self.chemistry,
            subject_code="p525",
            max_score=100,
            is_compulsory=False,
            order=2,
        )

    def _register_candidate_and_subject(self):
        register_eligible_candidates(self.session, dry_run=False)
        candidate = ExternalCandidate.objects.get(session=self.session, student=self.student)
        registration, _ = ExternalCandidateSubject.objects.get_or_create(
            candidate=candidate,
            subject=self.physics_subject,
        )
        return candidate, registration

    def test_candidate_bootstrap_is_dry_run_then_idempotent_and_does_not_enroll(self):
        preview = register_eligible_candidates(self.session, dry_run=True)
        self.assertEqual(preview["created_count"], 1)
        self.assertEqual(ExternalCandidate.objects.count(), 0)

        first = register_eligible_candidates(self.session, dry_run=False)
        second = register_eligible_candidates(self.session, dry_run=False)
        candidate = ExternalCandidate.objects.get()

        self.assertEqual(first["created_count"], 1)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(candidate.candidate_number, "UACE-0001")
        self.assertEqual(Enrollment.objects.count(), 0)
        self.assertEqual(ExamScore.objects.count(), 0)

    def test_bulk_subject_registration_adds_only_compulsory_subjects(self):
        candidate, _ = self._register_candidate_and_subject()
        ExternalCandidateSubject.objects.filter(candidate=candidate).delete()

        preview = register_compulsory_subjects(self.session, dry_run=True)
        applied = register_compulsory_subjects(self.session, dry_run=False)

        self.assertEqual(preview["created_count"], 1)
        self.assertEqual(applied["created_count"], 1)
        self.assertTrue(
            ExternalCandidateSubject.objects.filter(candidate=candidate, subject=self.physics_subject).exists()
        )
        self.assertFalse(
            ExternalCandidateSubject.objects.filter(candidate=candidate, subject=self.chemistry_subject).exists()
        )

    def test_candidate_export_uses_existing_learner_and_subject_records(self):
        candidate, registration = self._register_candidate_and_subject()

        exported = candidate_export_csv(self.session)

        self.assertIn("candidate_number,student_id,learner_id", exported)
        self.assertIn(candidate.candidate_number, exported)
        self.assertIn(self.student.student_id, exported)
        self.assertIn(self.physics_subject.subject_code, exported)
        self.assertTrue(ExternalCandidateSubject.objects.filter(pk=registration.pk).exists())

    def test_result_import_dry_run_then_commit_without_touching_internal_score(self):
        candidate, registration = self._register_candidate_and_subject()
        exam = Exam.objects.create(name="Internal Mock", term=self.term)
        paper = ExamPaper.objects.create(exam=exam, offering=self.offering, max_score=100)
        score = ExamScore.objects.create(paper=paper, student=self.student, score=61, percentage=61, grade="C")
        self.physics_subject.linked_paper = paper
        self.physics_subject.save(update_fields=["linked_paper", "updated_at"])
        csv_content = (
            "candidate_number,subject_code,score,percentage,grade,result_status,source_reference\n"
            f"{candidate.candidate_number},{self.physics_subject.subject_code},78,78,A,PASS,BOARD-1\n"
        ).encode()

        dry_run = import_external_results(
            self.session,
            SimpleUploadedFile("results.csv", csv_content, content_type="text/csv"),
            dry_run=True,
        )
        self.assertEqual(dry_run["accepted_count"], 1)
        self.assertEqual(ExternalExamResult.objects.count(), 0)
        self.assertEqual(ExternalResultImportBatch.objects.count(), 1)

        committed = import_external_results(
            self.session,
            SimpleUploadedFile("results.csv", csv_content, content_type="text/csv"),
            dry_run=False,
        )
        result = ExternalExamResult.objects.get(candidate_subject=registration)
        score.refresh_from_db()

        self.assertTrue(committed["committed"])
        self.assertEqual(result.score, Decimal("78"))
        self.assertEqual(result.grade, "A")
        self.assertEqual(result.result_status, ExternalExamResult.PASS)
        self.assertIsNone(result.linked_exam_score)
        self.assertEqual(score.score, Decimal("61"))
        self.assertEqual(score.grade, "C")

    def test_invalid_result_import_is_not_partially_committed(self):
        candidate, registration = self._register_candidate_and_subject()
        csv_content = (
            "candidate_number,subject_code,score,percentage,grade,result_status\n"
            f"{candidate.candidate_number},{self.physics_subject.subject_code},70,170,A,PASS\n"
        ).encode()

        summary = import_external_results(
            self.session,
            SimpleUploadedFile("invalid.csv", csv_content, content_type="text/csv"),
            dry_run=False,
        )

        self.assertFalse(summary["committed"])
        self.assertGreater(summary["rejected_count"], 0)
        self.assertTrue(summary["errors"])
        self.assertFalse(ExternalExamResult.objects.filter(candidate_subject=registration).exists())

    def test_optional_internal_score_link_validates_but_never_rewrites_score(self):
        candidate, registration = self._register_candidate_and_subject()
        exam = Exam.objects.create(name="Internal Final", term=self.term)
        paper = ExamPaper.objects.create(exam=exam, offering=self.offering, max_score=100)
        internal_score = ExamScore.objects.create(
            paper=paper,
            student=self.student,
            score=55,
            percentage=55,
            grade="D",
        )
        self.physics_subject.linked_paper = paper
        self.physics_subject.save(update_fields=["linked_paper", "updated_at"])

        external_result = ExternalExamResult(
            candidate_subject=registration,
            score=82,
            percentage=82,
            grade="A",
            result_status=ExternalExamResult.PASS,
            linked_exam_score=internal_score,
        )
        external_result.full_clean()
        external_result.save()
        internal_score.refresh_from_db()

        self.assertEqual(internal_score.score, Decimal("55"))
        self.assertEqual(internal_score.grade, "D")

    def test_readiness_accepts_complete_configuration(self):
        self._register_candidate_and_subject()

        readiness = external_exam_readiness()

        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["invalid_count"], 0)
        self.assertEqual(readiness["board_count"], 1)
        self.assertEqual(readiness["candidate_count"], 1)
