from django.test import TestCase

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Announcement
from .services import visible_announcements_for_user


class AnnouncementVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = OrganizationProfile.objects.create(name="Visibility School")
        cls.main = Campus.objects.create(
            organization=organization, name="Main", code="MAIN", is_default=True
        )
        cls.annex = Campus.objects.create(
            organization=organization, name="Annex", code="ANNEX"
        )
        cls.roles = {
            code: Role.objects.get_or_create(code=code, defaults={"name": label})[0]
            for code, label in Role.CODE_CHOICES
        }

    def _user(self, username, role):
        user = User.objects.create_user(username=username)
        UserRole.objects.create(user=user, role=self.roles[role])
        return user

    def test_teacher_sees_plural_teacher_audience_for_own_campus(self):
        user = self._user("teacher-visible", Role.TEACHER)
        TeacherProfile.objects.create(
            user=user, first_name="T", last_name="Main", campus=self.main
        )
        visible = Announcement.objects.create(
            title="Main teachers", body="Visible", audience=Announcement.TEACHERS, campus=self.main
        )
        Announcement.objects.create(
            title="Annex teachers", body="Hidden", audience=Announcement.TEACHERS, campus=self.annex
        )

        self.assertQuerySetEqual(visible_announcements_for_user(user), [visible])

    def test_school_wide_notice_is_visible_regardless_of_campus(self):
        user = self._user("student-visible", Role.STUDENT)
        StudentProfile.objects.create(
            user=user, first_name="S", last_name="Main", campus=self.main
        )
        notice = Announcement.objects.create(
            title="Everyone", body="Visible", audience=Announcement.ALL
        )

        self.assertIn(notice, visible_announcements_for_user(user))

    def test_parent_sees_notices_for_each_linked_child_campus(self):
        user = self._user("parent-visible", Role.PARENT)
        parent = ParentProfile.objects.create(user=user, first_name="P", last_name="One")
        for index, campus in enumerate((self.main, self.annex), start=1):
            student = StudentProfile.objects.create(
                first_name=f"Child{index}", last_name="One", campus=campus
            )
            ParentStudentLink.objects.create(parent=parent, student=student)
            Announcement.objects.create(
                title=f"Notice {index}", body="Visible", audience=Announcement.PARENTS, campus=campus
            )

        self.assertEqual(visible_announcements_for_user(user).count(), 2)

    def test_campus_admin_supports_multiple_explicit_assignments(self):
        user = User.objects.create_user(username="multi-campus-admin")
        for campus in (self.main, self.annex):
            UserRole.objects.create(
                user=user, role=self.roles[Role.CAMPUS_ADMIN], campus=campus
            )
            Announcement.objects.create(
                title=campus.name, body="Visible", audience=Announcement.ALL, campus=campus
            )

        self.assertEqual(visible_announcements_for_user(user).count(), 2)
