from django.test import TestCase

from apps.tenant.hr.models import StaffProfile
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import Role, User

from .models import TeacherProfile


class TeacherHrNormalizationTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()

    def test_teaching_staff_created_in_hr_appears_in_teachers(self):
        user = User.objects.create(username="hr_teacher", email="hr.teacher@example.com")

        staff = StaffProfile.objects.create(
            user=user,
            campus=self.campus,
            staff_id="HR-T-001",
            first_name="Harriet",
            last_name="Teacher",
            email="hr.teacher@example.com",
            staff_category=StaffProfile.TEACHING,
            is_active=True,
        )

        teacher = TeacherProfile.objects.get(user=user)
        self.assertEqual(teacher.staff_id, staff.staff_id)
        self.assertEqual(teacher.campus, staff.campus)
        self.assertEqual(teacher.first_name, staff.first_name)
        self.assertTrue(user.has_role(Role.TEACHER))

    def test_teacher_created_in_academics_appears_in_hr(self):
        user = User.objects.create(username="academic_teacher", email="academic.teacher@example.com")

        teacher = TeacherProfile.objects.create(
            user=user,
            campus=self.campus,
            staff_id="AC-T-001",
            first_name="Alice",
            last_name="Tutor",
            email="academic.teacher@example.com",
            is_active=True,
        )

        staff = StaffProfile.objects.get(user=user)
        self.assertEqual(staff.staff_id, teacher.staff_id)
        self.assertEqual(staff.staff_category, StaffProfile.TEACHING)
        self.assertEqual(staff.campus, teacher.campus)
        self.assertTrue(user.has_role(Role.TEACHER))

    def test_hr_edit_updates_existing_teacher_instead_of_creating_duplicate(self):
        staff = StaffProfile.objects.create(
            campus=self.campus,
            staff_id="SYNC-001",
            first_name="Original",
            last_name="Name",
            staff_category=StaffProfile.TEACHING,
        )
        teacher = TeacherProfile.objects.get(staff_id="SYNC-001", campus=self.campus)

        staff.first_name = "Updated"
        staff.phone = "+256700000001"
        staff.save()

        teacher.refresh_from_db()
        self.assertEqual(teacher.first_name, "Updated")
        self.assertEqual(teacher.phone, "+256700000001")
        self.assertEqual(TeacherProfile.objects.filter(staff_id="SYNC-001").count(), 1)

    def test_teacher_edit_updates_existing_hr_record_instead_of_creating_duplicate(self):
        teacher = TeacherProfile.objects.create(
            campus=self.campus,
            staff_id="SYNC-002",
            first_name="Teacher",
            last_name="Original",
        )
        staff = StaffProfile.objects.get(staff_id="SYNC-002", campus=self.campus)

        teacher.last_name = "Updated"
        teacher.email = "teacher.updated@example.com"
        teacher.save()

        staff.refresh_from_db()
        self.assertEqual(staff.last_name, "Updated")
        self.assertEqual(staff.email, "teacher.updated@example.com")
        self.assertEqual(StaffProfile.objects.filter(staff_id="SYNC-002").count(), 1)

    def test_non_teaching_staff_without_teacher_role_is_removed_from_active_teachers(self):
        staff = StaffProfile.objects.create(
            campus=self.campus,
            staff_id="SYNC-003",
            first_name="Former",
            last_name="Teacher",
            staff_category=StaffProfile.TEACHING,
            is_active=True,
        )
        teacher = TeacherProfile.objects.get(staff_id="SYNC-003", campus=self.campus)

        staff.staff_category = StaffProfile.NON_TEACHING
        staff.save()

        teacher.refresh_from_db()
        self.assertFalse(teacher.is_active)

    def test_records_without_staff_number_or_email_do_not_duplicate_on_edit(self):
        staff = StaffProfile.objects.create(
            campus=self.campus,
            first_name="No",
            last_name="Identifier",
            staff_category=StaffProfile.TEACHING,
        )
        self.assertEqual(TeacherProfile.objects.filter(first_name="No", last_name="Identifier").count(), 1)

        staff.phone = "+256700000002"
        staff.save()

        self.assertEqual(TeacherProfile.objects.filter(first_name="No", last_name="Identifier").count(), 1)
        self.assertEqual(
            TeacherProfile.objects.get(first_name="No", last_name="Identifier").phone,
            "+256700000002",
        )
