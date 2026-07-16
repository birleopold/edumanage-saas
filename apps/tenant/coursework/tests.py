from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Stream
from apps.tenant.coursework.models import Assignment, AssignmentSubmission, LearningMaterial
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User


class CourseworkAccessControlTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(organization=org, name="Other Coursework Campus")

        self.year = AcademicYear.objects.create(name="2026")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.course = Course.objects.create(name="Mathematics", code="MATH")

        self.class_group = ClassGroup.objects.create(campus=self.campus, name="Senior One")
        self.other_class_group = ClassGroup.objects.create(campus=self.other_campus, name="Senior Two")
        self.stream = Stream.objects.create(class_group=self.class_group, name="A")
        self.other_stream = Stream.objects.create(class_group=self.other_class_group, name="B")

        self.student_user = self._user_with_role("student_user", Role.STUDENT)
        self.other_student_user = self._user_with_role("other_student_user", Role.STUDENT)
        self.parent_user = self._user_with_role("parent_user", Role.PARENT)
        self.teacher_user = self._user_with_role("teacher_user", Role.TEACHER)
        self.other_teacher_user = self._user_with_role("other_teacher_user", Role.TEACHER)

        self.teacher = TeacherProfile.objects.create(
            user=self.teacher_user,
            campus=self.campus,
            first_name="Tina",
            last_name="Teacher",
        )
        self.other_teacher = TeacherProfile.objects.create(
            user=self.other_teacher_user,
            campus=self.other_campus,
            first_name="Oscar",
            last_name="Other",
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            campus=self.campus,
            stream=self.stream,
            first_name="Amina",
            last_name="Learner",
            student_id="CW-001",
        )
        self.other_student = StudentProfile.objects.create(
            user=self.other_student_user,
            campus=self.other_campus,
            stream=self.other_stream,
            first_name="Brian",
            last_name="Learner",
            student_id="CW-002",
        )
        self.parent = ParentProfile.objects.create(
            user=self.parent_user,
            first_name="Pat",
            last_name="Parent",
        )
        ParentStudentLink.objects.create(parent=self.parent, student=self.student, is_primary=True)

        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.term,
            class_group=self.class_group,
            teacher=self.teacher,
        )
        self.other_offering = CourseOffering.objects.create(
            campus=self.other_campus,
            course=self.course,
            term=self.term,
            class_group=self.other_class_group,
            teacher=self.other_teacher,
        )
        Enrollment.objects.create(campus=self.campus, offering=self.offering, student=self.student)
        Enrollment.objects.create(campus=self.other_campus, offering=self.other_offering, student=self.other_student)

        self.material = LearningMaterial.objects.create(
            type=LearningMaterial.NOTES,
            title="Visible notes",
            campus=self.campus,
            class_group=self.class_group,
            offering=self.offering,
            publish_at=timezone.now(),
            created_by=self.teacher_user,
        )
        self.other_material = LearningMaterial.objects.create(
            type=LearningMaterial.NOTES,
            title="Hidden notes",
            campus=self.other_campus,
            class_group=self.other_class_group,
            offering=self.other_offering,
            publish_at=timezone.now(),
            created_by=self.other_teacher_user,
        )
        self.assignment = Assignment.objects.create(
            title="Visible assignment",
            campus=self.campus,
            class_group=self.class_group,
            offering=self.offering,
            publish_at=timezone.now(),
            max_score=Decimal("100"),
            created_by=self.teacher_user,
        )
        self.other_assignment = Assignment.objects.create(
            title="Hidden assignment",
            campus=self.other_campus,
            class_group=self.other_class_group,
            offering=self.other_offering,
            publish_at=timezone.now(),
            max_score=Decimal("100"),
            created_by=self.other_teacher_user,
        )
        self.other_submission = AssignmentSubmission.objects.create(
            assignment=self.other_assignment,
            student=self.other_student,
            submitted_at=timezone.now(),
            text_answer="private submission",
        )

    def _user_with_role(self, username: str, role_code: str) -> User:
        role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code.title()})
        user = User.objects.create_user(username=username, password="test-pass-123")
        user.roles.add(role)
        return user

    def test_student_cannot_force_browse_other_coursework_items(self):
        self.client.login(username="student_user", password="test-pass-123")

        material_response = self.client.get(reverse("student_coursework_material_detail", kwargs={"pk": self.other_material.pk}))
        assignment_response = self.client.get(reverse("student_coursework_assignment_detail", kwargs={"pk": self.other_assignment.pk}))
        submit_response = self.client.post(reverse("student_coursework_assignment_submit", kwargs={"pk": self.other_assignment.pk}), {"text_answer": "forged"})

        self.assertEqual(material_response.status_code, 403)
        self.assertEqual(assignment_response.status_code, 403)
        self.assertEqual(submit_response.status_code, 403)
        self.assertFalse(
            AssignmentSubmission.objects.filter(
                assignment=self.other_assignment,
                student=self.student,
                text_answer="forged",
            ).exists()
        )

    def test_parent_cannot_force_browse_coursework_not_assigned_to_child(self):
        self.client.login(username="parent_user", password="test-pass-123")

        material_response = self.client.get(
            reverse(
                "parent_coursework_material_detail",
                kwargs={"student_id": self.student.pk, "pk": self.other_material.pk},
            )
        )
        assignment_response = self.client.get(
            reverse(
                "parent_coursework_assignment_detail",
                kwargs={"student_id": self.student.pk, "pk": self.other_assignment.pk},
            )
        )

        self.assertEqual(material_response.status_code, 403)
        self.assertEqual(assignment_response.status_code, 403)

    def test_parent_cannot_force_browse_unlinked_student_coursework(self):
        self.client.login(username="parent_user", password="test-pass-123")

        response = self.client.get(
            reverse(
                "parent_coursework_assignment_detail",
                kwargs={"student_id": self.other_student.pk, "pk": self.other_assignment.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_force_browse_or_mark_other_teacher_assignment(self):
        self.client.login(username="teacher_user", password="test-pass-123")

        detail_response = self.client.get(reverse("teacher_coursework_assignment_detail", kwargs={"pk": self.other_assignment.pk}))
        submissions_response = self.client.get(reverse("teacher_coursework_assignment_submissions", kwargs={"pk": self.other_assignment.pk}))
        mark_response = self.client.post(
            reverse(
                "teacher_coursework_submission_mark",
                kwargs={"assignment_id": self.other_assignment.pk, "submission_id": self.other_submission.pk},
            ),
            {"score": "99", "feedback": "forged"},
        )

        self.assertEqual(detail_response.status_code, 403)
        self.assertEqual(submissions_response.status_code, 403)
        self.assertEqual(mark_response.status_code, 403)
        self.other_submission.refresh_from_db()
        self.assertIsNone(self.other_submission.score)
        self.assertEqual(self.other_submission.feedback, "")

    def test_teacher_cannot_force_browse_other_teacher_material(self):
        self.client.login(username="teacher_user", password="test-pass-123")

        detail_response = self.client.get(reverse("teacher_coursework_material_detail", kwargs={"pk": self.other_material.pk}))
        edit_response = self.client.get(reverse("teacher_coursework_material_edit", kwargs={"pk": self.other_material.pk}))

        self.assertEqual(detail_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 403)
