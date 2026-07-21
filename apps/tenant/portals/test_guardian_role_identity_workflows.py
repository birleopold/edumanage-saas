from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.parents.services import link_parent_to_student
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role


class GuardianRoleIdentityWorkflowTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        if not self.campus:
            self.campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                code="MAIN",
                is_default=True,
                is_active=True,
            )
        self.admin = get_user_model().objects.create_superuser(
            username="guardian-admin",
            email="guardian-admin@example.com",
            password="test-password",
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="STU-001",
            first_name="Bob",
            last_name="Johnson",
            email="bob@example.com",
        )

    def test_parent_creation_requires_and_saves_student_relationship(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin_parents_create"),
            {
                "first_name": "Grace",
                "last_name": "Johnson",
                "phone": "0700000000",
                "email": "grace@example.com",
                "student": self.student.pk,
                "relationship": "Mother",
                "is_primary_guardian": "on",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        parent = ParentProfile.objects.get(email="grace@example.com")
        link = ParentStudentLink.objects.get(parent=parent, student=self.student)
        self.assertEqual(link.relationship, "Mother")
        self.assertTrue(link.is_primary)

    def test_new_primary_guardian_replaces_the_previous_primary_only(self):
        first = ParentProfile.objects.create(
            first_name="First",
            last_name="Guardian",
        )
        second = ParentProfile.objects.create(
            first_name="Second",
            last_name="Guardian",
        )
        link_parent_to_student(
            parent=first,
            student=self.student,
            relationship="Father",
            is_primary=True,
        )
        link_parent_to_student(
            parent=second,
            student=self.student,
            relationship="Mother",
            is_primary=True,
        )

        self.assertFalse(
            ParentStudentLink.objects.get(parent=first, student=self.student).is_primary
        )
        self.assertTrue(
            ParentStudentLink.objects.get(parent=second, student=self.student).is_primary
        )
        self.assertEqual(
            ParentStudentLink.objects.filter(student=self.student, is_primary=True).count(),
            1,
        )

    def test_student_administrator_page_exposes_guardian_management(self):
        parent = ParentProfile.objects.create(
            first_name="Alice",
            last_name="Johnson",
            phone="0711111111",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin_student_guardians", args=[self.student.pk]),
            {
                "parent": parent.pk,
                "relationship": "Guardian",
                "is_primary": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice")
        self.assertContains(response, "Guardian")
        self.assertTrue(
            ParentStudentLink.objects.filter(
                parent=parent,
                student=self.student,
                is_primary=True,
            ).exists()
        )

    def test_student_profile_uses_student_portal_and_school_managed_names(self):
        role, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        user = get_user_model().objects.create_user(
            username="STU-001",
            password="test-password",
        )
        user.roles.add(role)
        self.student.user = user
        self.student.save(update_fields=["user"])
        get_user_model().objects.filter(pk=user.pk).update(
            first_name="",
            last_name="",
            email="",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("user_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portals/student/base.html")
        self.assertContains(response, "Student account")
        self.assertContains(response, "Bob Johnson")
        self.assertContains(response, reverse("student_home"))
        self.assertNotContains(response, "Administrator account")
        self.assertNotContains(response, reverse("audit_two_factor_settings"))
        self.assertContains(response, 'name="first_name"', html=False)
        self.assertContains(response, "disabled", html=False)

    def test_student_cannot_change_school_names_from_shared_profile(self):
        user = get_user_model().objects.create_user(
            username="STU-EDIT",
            password="test-password",
        )
        role, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        user.roles.add(role)
        self.student.user = user
        self.student.save(update_fields=["user"])
        self.client.force_login(user)

        response = self.client.post(
            reverse("user_profile"),
            {
                "first_name": "Different",
                "last_name": "Person",
                "email": "new-bob@example.com",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(self.student.first_name, "Bob")
        self.assertEqual(self.student.last_name, "Johnson")
        self.assertEqual(user.first_name, "Bob")
        self.assertEqual(user.last_name, "Johnson")
        self.assertEqual(self.student.email, "new-bob@example.com")
        self.assertEqual(user.email, "new-bob@example.com")

    def test_student_creation_signal_populates_login_identity_and_role(self):
        Role.objects.filter(code=Role.STUDENT).delete()
        user = get_user_model().objects.create_user(
            username="AUTO-STUDENT",
            password="test-password",
        )

        learner = StudentProfile.objects.create(
            user=user,
            campus=self.campus,
            student_id="AUTO-STUDENT",
            first_name="Amina",
            last_name="Nabirye",
            email="amina@example.com",
        )

        user.refresh_from_db()
        self.assertEqual(user.first_name, "Amina")
        self.assertEqual(user.last_name, "Nabirye")
        self.assertEqual(user.email, "amina@example.com")
        self.assertTrue(user.has_role(Role.STUDENT))
        self.assertEqual(learner.first_name, "Amina")

    def test_login_repairs_an_older_blank_student_account(self):
        user = get_user_model().objects.create_user(
            username="OLD-STUDENT",
            password="test-password",
        )
        role, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        user.roles.add(role)
        self.student.user = user
        self.student.save(update_fields=["user"])
        get_user_model().objects.filter(pk=user.pk).update(
            first_name="",
            last_name="",
            email="",
        )

        self.assertTrue(
            self.client.login(username="OLD-STUDENT", password="test-password")
        )

        user.refresh_from_db()
        self.assertEqual(user.first_name, "Bob")
        self.assertEqual(user.last_name, "Johnson")
        self.assertEqual(user.email, "bob@example.com")
