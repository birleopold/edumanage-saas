from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.models import Notification
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import SickbayVisit, StudentMedicalProfile


class SickbayAdminTests(TestCase):
    def setUp(self):
        admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin"})
        self.user = User.objects.create_user(username="sickbay_admin", password="test-pass-123")
        self.user.roles.add(admin_role)
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            first_name="Care",
            last_name="Learner",
            student_id="MED-001",
            campus=self.campus,
        )

    def test_dashboard_renders_for_admin(self):
        self.client.login(username="sickbay_admin", password="test-pass-123")
        response = self.client.get(reverse("admin_sickbay_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sickbay operations")

    def test_admin_can_record_sickbay_visit(self):
        self.client.login(username="sickbay_admin", password="test-pass-123")
        response = self.client.post(
            reverse("admin_sickbay_visit_create"),
            {
                "student": self.student.pk,
                "severity": SickbayVisit.MODERATE,
                "complaint": "Headache",
                "symptoms": "Headache and dizziness",
                "temperature_c": "37.8",
                "nurse_or_doctor_name": "Nurse Jane",
                "treatment_given": "Rest and water",
                "medicine_given": "Paracetamol",
                "dosage": "One tablet",
                "parent_notified": "on",
                "parent_notification_method": "PHONE",
                "outcome": SickbayVisit.RETURNED_TO_CLASS,
                "follow_up_required": "",
                "follow_up_note": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        visit = SickbayVisit.objects.get()
        self.assertEqual(visit.student, self.student)
        self.assertEqual(visit.campus, self.campus)
        self.assertTrue(visit.parent_notified)
        self.assertIsNotNone(visit.parent_notified_at)

    def test_medical_profile_alerts_show_on_profile_list(self):
        StudentMedicalProfile.objects.create(
            student=self.student,
            allergies="Penicillin",
            emergency_contact_name="Parent Care",
            emergency_contact_phone="0772000000",
        )

        self.client.login(username="sickbay_admin", password="test-pass-123")
        response = self.client.get(reverse("admin_sickbay_profile_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Medical alert")
        self.assertContains(response, "Learner Care")

    def test_campus_admin_sees_only_their_campus_sickbay_visits(self):
        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        campus_user = User.objects.create_user(username="sickbay_campus_admin", password="test-pass-123")
        campus_user.roles.add(campus_role)
        UserRole.objects.create(user=campus_user, role=campus_role, campus=self.campus)
        other_campus = Campus.objects.create(
            organization=self.campus.organization,
            name="Other Sickbay Campus",
            is_active=True,
        )
        other_student = StudentProfile.objects.create(
            first_name="Other",
            last_name="Clinic",
            student_id="MED-OTHER",
            campus=other_campus,
        )
        SickbayVisit.objects.create(student=self.student, complaint="Visible headache")
        hidden_visit = SickbayVisit.objects.create(student=other_student, complaint="Hidden fever")

        self.client.login(username="sickbay_campus_admin", password="test-pass-123")
        dashboard = self.client.get(reverse("admin_sickbay_dashboard"))
        visit_list = self.client.get(reverse("admin_sickbay_visit_list"))
        hidden_detail = self.client.get(reverse("admin_sickbay_visit_detail", kwargs={"pk": hidden_visit.pk}))

        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Visible headache")
        self.assertNotContains(dashboard, "Hidden fever")
        self.assertContains(visit_list, "Visible headache")
        self.assertNotContains(visit_list, "Hidden fever")
        self.assertEqual(hidden_detail.status_code, 404)

    def test_campus_admin_cannot_record_visit_for_other_campus_student(self):
        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        campus_user = User.objects.create_user(username="sickbay_campus_create", password="test-pass-123")
        campus_user.roles.add(campus_role)
        UserRole.objects.create(user=campus_user, role=campus_role, campus=self.campus)
        other_campus = Campus.objects.create(
            organization=self.campus.organization,
            name="Other Sickbay Create Campus",
            is_active=True,
        )
        other_student = StudentProfile.objects.create(
            first_name="Other",
            last_name="Create",
            student_id="MED-CREATE-OTHER",
            campus=other_campus,
        )

        self.client.login(username="sickbay_campus_create", password="test-pass-123")
        response = self.client.post(
            reverse("admin_sickbay_visit_create"),
            {
                "student": other_student.pk,
                "severity": SickbayVisit.MODERATE,
                "complaint": "Should not save",
                "outcome": SickbayVisit.RETURNED_TO_CLASS,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SickbayVisit.objects.filter(complaint="Should not save").exists())


class ParentSickbayTests(TestCase):
    def setUp(self):
        parent_role, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
        admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin"})
        self.parent_user = User.objects.create_user(username="sickbay_parent", password="test-pass-123")
        self.parent_user.roles.add(parent_role)
        self.admin_user = User.objects.create_user(username="sickbay_notify_admin", password="test-pass-123")
        self.admin_user.roles.add(admin_role)
        self.parent = ParentProfile.objects.create(user=self.parent_user, first_name="Pat", last_name="Health")
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Child",
            student_id="MED-P-001",
            campus=self.campus,
        )
        self.other_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Child",
            student_id="MED-P-002",
            campus=self.campus,
        )
        ParentStudentLink.objects.create(parent=self.parent, student=self.student, is_primary=True)

    def test_parent_sees_only_linked_child_sickbay_visits(self):
        SickbayVisit.objects.create(
            student=self.student,
            complaint="Stomach pain",
            symptoms="Mild stomach pain",
            outcome=SickbayVisit.RETURNED_TO_CLASS,
        )
        SickbayVisit.objects.create(
            student=self.other_student,
            complaint="Hidden complaint",
            outcome=SickbayVisit.RETURNED_TO_CLASS,
        )
        StudentMedicalProfile.objects.create(student=self.student, allergies="Peanuts")

        self.client.login(username="sickbay_parent", password="test-pass-123")
        response = self.client.get(reverse("parent_sickbay_visits"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stomach pain")
        self.assertContains(response, "Peanuts")
        self.assertNotContains(response, "Hidden complaint")

    def test_recording_parent_notified_creates_parent_portal_notification(self):
        self.client.login(username="sickbay_notify_admin", password="test-pass-123")
        response = self.client.post(
            reverse("admin_sickbay_visit_create"),
            {
                "student": self.student.pk,
                "severity": SickbayVisit.SEVERE,
                "complaint": "Fever",
                "symptoms": "High temperature",
                "nurse_or_doctor_name": "Nurse Jane",
                "treatment_given": "Rest and observation",
                "parent_notified": "on",
                "parent_notification_method": "PHONE",
                "outcome": SickbayVisit.SENT_HOME,
                "follow_up_required": "on",
                "follow_up_note": "Monitor overnight",
            },
        )

        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(recipient=self.parent_user)
        self.assertEqual(notification.audience, Notification.PARENTS)
        self.assertEqual(notification.priority, Notification.URGENT)
        self.assertEqual(notification.link, reverse("parent_sickbay_visits"))


class StudentSickbayTests(TestCase):
    def setUp(self):
        student_role, _ = Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})
        self.user = User.objects.create_user(username="sickbay_student", password="test-pass-123")
        self.user.roles.add(student_role)
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            user=self.user,
            first_name="Self",
            last_name="Care",
            student_id="MED-S-001",
            campus=self.campus,
        )
        self.other_student = StudentProfile.objects.create(
            first_name="Other",
            last_name="Care",
            student_id="MED-S-002",
            campus=self.campus,
        )

    def test_student_sees_only_own_sickbay_visits_and_profile(self):
        StudentMedicalProfile.objects.create(student=self.student, allergies="Dust")
        SickbayVisit.objects.create(
            student=self.student,
            complaint="Cough",
            symptoms="Dry cough",
            treatment_given="Warm water",
            outcome=SickbayVisit.RETURNED_TO_CLASS,
        )
        SickbayVisit.objects.create(
            student=self.other_student,
            complaint="Hidden cough",
            outcome=SickbayVisit.RETURNED_TO_CLASS,
        )

        self.client.login(username="sickbay_student", password="test-pass-123")
        response = self.client.get(reverse("student_sickbay_visits"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cough")
        self.assertContains(response, "Dust")
        self.assertNotContains(response, "Hidden cough")
