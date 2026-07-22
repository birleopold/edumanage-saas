from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.parents.models import ParentProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Poll, PollOption


class PollPortalAndCampusHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = OrganizationProfile.objects.create(name="Poll Hardening School")
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
            username="poll-campus-admin",
            password="StrongPass123!",
        )
        UserRole.objects.create(
            user=cls.campus_admin,
            role=cls.roles[Role.CAMPUS_ADMIN],
            campus=cls.campus_one,
        )

        cls.parent_user = User.objects.create_user(
            username="poll-parent",
            password="StrongPass123!",
        )
        cls.parent_user.roles.add(cls.roles[Role.PARENT])
        ParentProfile.objects.create(
            user=cls.parent_user,
            first_name="Pat",
            last_name="Parent",
        )

        cls.teacher_user = User.objects.create_user(
            username="poll-teacher",
            password="StrongPass123!",
        )
        cls.teacher_user.roles.add(cls.roles[Role.TEACHER])
        cls.teacher = TeacherProfile.objects.create(
            user=cls.teacher_user,
            campus=cls.campus_one,
            first_name="Tina",
            last_name="Teacher",
        )
        cls.student = StudentProfile.objects.create(
            campus=cls.campus_one,
            first_name="Sam",
            last_name="Student",
            student_id="ST-POLL-1",
        )
        cls.other_student = StudentProfile.objects.create(
            campus=cls.campus_two,
            first_name="Other",
            last_name="Student",
            student_id="ST-POLL-2",
        )

        cls.poll_one = Poll.objects.create(
            title="Main Campus Poll",
            campus=cls.campus_one,
            audience=Poll.ALL,
            is_active=True,
        )
        PollOption.objects.create(poll=cls.poll_one, option_text="Yes", order=1)
        cls.poll_two = Poll.objects.create(
            title="Other Campus Poll",
            campus=cls.campus_two,
            audience=Poll.ALL,
            is_active=True,
        )
        PollOption.objects.create(poll=cls.poll_two, option_text="No", order=1)

    def test_shared_poll_pages_keep_parent_and_teacher_shells(self):
        for user, expected_template in (
            (self.parent_user, "portals/parent/base.html"),
            (self.teacher_user, "portals/teacher/base.html"),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("poll_list"))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, expected_template)
                self.client.logout()

    def test_campus_admin_poll_management_is_campus_scoped(self):
        self.client.force_login(self.campus_admin)
        response = self.client.get(reverse("admin_poll_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["polls"]), [self.poll_one])
        cross_campus = self.client.get(
            reverse("admin_poll_detail", kwargs={"pk": self.poll_two.pk})
        )
        self.assertEqual(cross_campus.status_code, 404)

    def test_campus_admin_poll_form_rejects_cross_campus_targets(self):
        self.client.force_login(self.campus_admin)
        response = self.client.post(
            reverse("admin_poll_create"),
            {
                "title": "Tampered Poll",
                "campus": self.campus_two.pk,
                "audience": Poll.STUDENTS,
                "specific_students": [self.other_student.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Poll.objects.filter(title="Tampered Poll").exists())
