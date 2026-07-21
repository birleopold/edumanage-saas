from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.hostels.hardening_models import GuardianContactLog
from apps.tenant.hostels.models import Bed, BedAllocation, BoardingLeave, Hostel, HostelRoom
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.bulk_import import ImportRow, process_bulk_import
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role


class ParentStudentRelationshipUiTests(TestCase):
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
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="LINK-001",
            first_name="Amina",
            last_name="Learner",
            email="amina@example.com",
        )
        self.admin = get_user_model().objects.create_superuser(
            username="relationship-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(self.admin)

    def test_parent_is_created_with_visible_student_relationship(self):
        response = self.client.post(
            reverse("admin_parents_create"),
            {
                "first_name": "Grace",
                "last_name": "Guardian",
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

        registry = self.client.get(reverse("admin_parents_list"))
        self.assertContains(registry, "Amina")
        self.assertContains(registry, "Mother")
        self.assertContains(registry, "Primary")

    def test_guardian_contact_can_select_only_a_parent_linked_to_the_student(self):
        linked_parent = ParentProfile.objects.create(
            first_name="Grace",
            last_name="Guardian",
            phone="0700000000",
        )
        unrelated_parent = ParentProfile.objects.create(
            first_name="UnlinkedGuardianZZZ",
            last_name="Outside",
            phone="0711111111",
        )
        ParentStudentLink.objects.create(
            parent=linked_parent,
            student=self.student,
            relationship="Mother",
            is_primary=True,
        )

        hostel = Hostel.objects.create(name="Main House", code="MH")
        room = HostelRoom.objects.create(hostel=hostel, name="Room 1", capacity=1)
        bed = Bed.objects.create(room=room, label="A")
        allocation = BedAllocation.objects.create(bed=bed, student=self.student)
        now = timezone.now()
        leave = BoardingLeave.objects.create(
            student=self.student,
            bed_allocation=allocation,
            expected_departure_at=now + timedelta(hours=1),
            expected_return_at=now + timedelta(days=1),
            guardian_name="Grace Guardian",
            guardian_phone="0700000000",
        )

        form_page = self.client.get(reverse("admin_boarding_leave_contact", args=[leave.pk]))
        parent_queryset = form_page.context["form"].fields["parent"].queryset
        self.assertIn(linked_parent, parent_queryset)
        self.assertNotIn(unrelated_parent, parent_queryset)

        response = self.client.post(
            reverse("admin_boarding_leave_contact", args=[leave.pk]),
            {
                "parent": linked_parent.pk,
                "purpose": GuardianContactLog.LEAVE_APPROVAL,
                "method": GuardianContactLog.PHONE,
                "outcome": GuardianContactLog.CONFIRMED,
                "contact_name": "",
                "contact_phone": "",
                "occurred_at": now.strftime("%Y-%m-%dT%H:%M"),
                "note": "Confirmed collection.",
            },
        )

        self.assertEqual(response.status_code, 302)
        contact = GuardianContactLog.objects.get(boarding_leave=leave)
        self.assertEqual(contact.parent, linked_parent)
        self.assertEqual(contact.contact_name, str(linked_parent))
        self.assertEqual(contact.contact_phone, linked_parent.phone)


class RoleLockedStudentProfileTests(TestCase):
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
        role, _ = Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})
        self.user = get_user_model().objects.create_user(
            username="STU-001",
            password="test-password",
        )
        self.user.roles.add(role)
        self.student = StudentProfile.objects.create(
            user=self.user,
            campus=self.campus,
            student_id="STU-001",
            first_name="Bob",
            last_name="Johnson",
            email="bob@example.com",
        )

    def test_login_repairs_identity_and_profile_stays_in_student_portal(self):
        get_user_model().objects.filter(pk=self.user.pk).update(
            first_name="",
            last_name="",
            email="",
        )

        self.assertTrue(self.client.login(username="STU-001", password="test-password"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Bob")
        self.assertEqual(self.user.last_name, "Johnson")
        self.assertEqual(self.user.email, "bob@example.com")

        response = self.client.get(reverse("user_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_base_template"], "portals/student/base.html")
        self.assertEqual(response.context["role_label"], "Student")
        self.assertContains(response, "Bob")
        self.assertContains(response, "STU-001")
        self.assertContains(response, reverse("student_home"))
        self.assertNotContains(response, "Administrator account")

    def test_student_cannot_create_a_second_identity_from_the_account_page(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("user_profile"),
            {
                "first_name": "Different",
                "last_name": "Person",
                "email": "different@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.student.first_name, "Bob")
        self.assertEqual(self.student.last_name, "Johnson")
        self.assertEqual(self.user.first_name, "Bob")
        self.assertEqual(self.user.last_name, "Johnson")

    def test_student_record_edits_update_the_linked_login_identity(self):
        self.student.first_name = "Robert"
        self.student.last_name = "Johnson-Smith"
        self.student.email = "robert@example.com"
        self.student.save()

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Robert")
        self.assertEqual(self.user.last_name, "Johnson-Smith")
        self.assertEqual(self.user.email, "robert@example.com")


class BulkStudentIdentityTests(TestCase):
    def test_bulk_imported_login_uses_the_student_name_and_email(self):
        organization = get_or_create_organization()
        campus = Campus.objects.filter(organization=organization).first()
        if not campus:
            campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                code="MAIN",
                is_default=True,
                is_active=True,
            )
        Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})
        admin = get_user_model().objects.create_superuser(
            username="bulk-admin",
            email="bulk-admin@example.com",
            password="test-password",
        )

        result = process_bulk_import(
            rows=[
                ImportRow(
                    row_number=2,
                    first_name="Jane",
                    last_name="Namuli",
                    date_of_birth="2011-08-22",
                    email="jane@example.com",
                    campus_code="MAIN",
                    errors=[],
                )
            ],
            default_campus=campus,
            campus_map={"MAIN": campus},
            create_users=True,
            admin_user=admin,
        )

        self.assertEqual(result.successful, 1)
        student = result.students[0]
        user = student.user
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Namuli")
        self.assertEqual(user.email, "jane@example.com")
