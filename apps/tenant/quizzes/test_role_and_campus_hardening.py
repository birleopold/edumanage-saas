from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
)
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Quiz


class QuizRoleAndCampusHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = OrganizationProfile.objects.create(name="Quiz Hardening School")
        cls.campus_one = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        cls.campus_two = Campus.objects.create(
            organization=organization,
            name="Other Campus",
            code="OTHER",
        )
        cls.roles = {
            code: Role.objects.get_or_create(code=code, defaults={"name": label})[0]
            for code, label in Role.CODE_CHOICES
        }

        cls.campus_admin = User.objects.create_user(
            username="quiz-campus-admin",
            password="StrongPass123!",
        )
        UserRole.objects.create(
            user=cls.campus_admin,
            role=cls.roles[Role.CAMPUS_ADMIN],
            campus=cls.campus_one,
        )

        cls.principal = User.objects.create_user(
            username="quiz-principal",
            password="StrongPass123!",
        )
        cls.principal.roles.add(cls.roles[Role.PRINCIPAL])

        cls.teacher_user = User.objects.create_user(
            username="quiz-teacher",
            password="StrongPass123!",
        )
        cls.teacher_user.roles.add(cls.roles[Role.TEACHER])
        cls.teacher = TeacherProfile.objects.create(
            user=cls.teacher_user,
            campus=cls.campus_one,
            first_name="Tina",
            last_name="Teacher",
        )

        cls.other_teacher_user = User.objects.create_user(
            username="other-quiz-teacher",
            password="StrongPass123!",
        )
        cls.other_teacher_user.roles.add(cls.roles[Role.TEACHER])
        cls.other_teacher = TeacherProfile.objects.create(
            user=cls.other_teacher_user,
            campus=cls.campus_two,
            first_name="Other",
            last_name="Teacher",
        )

        cls.student_user = User.objects.create_user(
            username="quiz-student",
            password="StrongPass123!",
        )
        cls.student_user.roles.add(cls.roles[Role.STUDENT])
        cls.student = StudentProfile.objects.create(
            user=cls.student_user,
            campus=cls.campus_one,
            first_name="Sam",
            last_name="Student",
            student_id="ST-001",
        )
        cls.other_student = StudentProfile.objects.create(
            campus=cls.campus_two,
            first_name="Other",
            last_name="Student",
            student_id="ST-002",
        )

        cls.student_without_profile = User.objects.create_user(
            username="student-without-profile",
            password="StrongPass123!",
        )
        cls.student_without_profile.roles.add(cls.roles[Role.STUDENT])

        year = AcademicYear.objects.create(
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        term = AcademicTerm.objects.create(year=year, name="Term 1", order=1, is_current=True)
        course = Course.objects.create(name="Mathematics", code="MATH")
        cls.class_one = ClassGroup.objects.create(campus=cls.campus_one, name="Senior One")
        cls.class_two = ClassGroup.objects.create(campus=cls.campus_two, name="Senior Two")
        cls.offering_one = CourseOffering.objects.create(
            campus=cls.campus_one,
            course=course,
            term=term,
            class_group=cls.class_one,
            teacher=cls.teacher,
        )
        cls.offering_two = CourseOffering.objects.create(
            campus=cls.campus_two,
            course=course,
            term=term,
            class_group=cls.class_two,
            teacher=cls.other_teacher,
        )
        Enrollment.objects.create(
            campus=cls.campus_one,
            offering=cls.offering_one,
            student=cls.student,
            status=Enrollment.ACTIVE,
        )

        cls.quiz_one = Quiz.objects.create(
            name="Main Campus Quiz",
            campus=cls.campus_one,
            course_offering=cls.offering_one,
            created_by=cls.teacher_user,
        )
        cls.quiz_two = Quiz.objects.create(
            name="Other Campus Quiz",
            campus=cls.campus_two,
            course_offering=cls.offering_two,
            created_by=cls.other_teacher_user,
        )

    def test_campus_admin_keeps_admin_shell_and_only_sees_own_campus(self):
        self.client.force_login(self.campus_admin)
        response = self.client.get(reverse("teacher_quiz_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portals/admin/base.html")
        self.assertTemplateNotUsed(response, "portals/teacher/base.html")
        self.assertEqual(list(response.context["quizzes"]), [self.quiz_one])

        forbidden = self.client.get(
            reverse("teacher_quiz_detail", kwargs={"pk": self.quiz_two.pk})
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_principal_uses_admin_shell_and_has_tenant_wide_quiz_scope(self):
        self.client.force_login(self.principal)
        response = self.client.get(reverse("teacher_quiz_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portals/admin/base.html")
        self.assertEqual(
            set(response.context["quizzes"].values_list("pk", flat=True)),
            {self.quiz_one.pk, self.quiz_two.pk},
        )

    def test_teacher_keeps_teacher_shell_and_only_sees_own_quizzes(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse("teacher_quiz_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portals/teacher/base.html")
        self.assertEqual(list(response.context["quizzes"]), [self.quiz_one])

    def test_campus_admin_form_rejects_cross_campus_tampering(self):
        self.client.force_login(self.campus_admin)
        response = self.client.post(
            reverse("teacher_quiz_create"),
            {
                "name": "Tampered Quiz",
                "campus": self.campus_two.pk,
                "course_offering": self.offering_two.pk,
                "time_limit_minutes": 30,
                "difficulty": Quiz.MEDIUM,
                "students": [self.other_student.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Quiz.objects.filter(name="Tampered Quiz").exists())

    def test_student_without_profile_gets_not_found_instead_of_server_error(self):
        self.client.force_login(self.student_without_profile)
        response = self.client.get(
            reverse("student_quiz_take", kwargs={"pk": self.quiz_one.pk})
        )
        self.assertEqual(response.status_code, 404)
