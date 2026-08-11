from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.orgsettings.services import SESSION_CURRENT_CAMPUS_ID
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Stream


class AcademicsCampusScopeTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Scope Test School")
        self.campus_a = Campus.objects.create(
            organization=self.organization,
            name="Campus A",
            code="A",
            is_default=True,
        )
        self.campus_b = Campus.objects.create(
            organization=self.organization,
            name="Campus B",
            code="B",
        )

        self.role, _created = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        self.user = User.objects.create_user(username="campus-a-admin", password="test-pass-123")
        UserRole.objects.create(user=self.user, role=self.role, campus=self.campus_a)
        self.client.force_login(self.user)

        self.year = AcademicYear.objects.create(name="2026", is_current=True)
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1, is_current=True)
        self.course = Course.objects.create(name="Mathematics", code="MATH")

        self.class_a = ClassGroup.objects.create(campus=self.campus_a, name="Form 1 A", code="F1A")
        self.class_b = ClassGroup.objects.create(campus=self.campus_b, name="Form 1 B", code="F1B")
        self.stream_a = Stream.objects.create(class_group=self.class_a, name="Blue", capacity=40)
        self.stream_b = Stream.objects.create(class_group=self.class_b, name="Red", capacity=40)

        self.student_a = StudentProfile.objects.create(
            campus=self.campus_a,
            stream=self.stream_a,
            student_id="A-001",
            first_name="Amina",
            last_name="Nabirye",
        )
        self.student_b = StudentProfile.objects.create(
            campus=self.campus_b,
            stream=self.stream_b,
            student_id="B-001",
            first_name="Brian",
            last_name="Okello",
        )

        self.offering_a = CourseOffering.objects.create(
            campus=self.campus_a,
            course=self.course,
            term=self.term,
            class_group=self.class_a,
        )
        self.offering_b = CourseOffering.objects.create(
            campus=self.campus_b,
            course=self.course,
            term=self.term,
            class_group=self.class_b,
        )
        self.enrollment_a = Enrollment.objects.create(
            campus=self.campus_a,
            offering=self.offering_a,
            student=self.student_a,
        )
        self.enrollment_b = Enrollment.objects.create(
            campus=self.campus_b,
            offering=self.offering_b,
            student=self.student_b,
        )

    def test_class_group_list_ignores_crafted_other_campus_filter(self):
        response = self.client.get(reverse("admin_classgroup_list"), {"campus": self.campus_b.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Form 1 A")
        self.assertNotContains(response, "Form 1 B")

    def test_other_campus_objects_cannot_be_edited_directly(self):
        self.assertEqual(
            self.client.get(reverse("admin_classgroup_edit", args=[self.class_b.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("admin_offering_edit", args=[self.offering_b.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("admin_enrollment_edit", args=[self.enrollment_b.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("admin_stream_edit", args=[self.stream_b.pk])).status_code,
            404,
        )

    def test_bulk_enrollment_rejects_cross_campus_student_atomically(self):
        local_new = StudentProfile.objects.create(
            campus=self.campus_a,
            student_id="A-002",
            first_name="Grace",
            last_name="Kato",
        )
        remote_new = StudentProfile.objects.create(
            campus=self.campus_b,
            student_id="B-002",
            first_name="David",
            last_name="Ouma",
        )

        response = self.client.post(
            reverse("admin_enrollment_bulk"),
            {
                "offering": self.offering_a.pk,
                "student_ids": [local_new.pk, remote_new.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Enrollment.objects.filter(offering=self.offering_a, student=local_new).exists())
        self.assertFalse(Enrollment.objects.filter(offering=self.offering_a, student=remote_new).exists())

    def test_bulk_status_cannot_select_other_campus_offering(self):
        response = self.client.get(
            reverse("admin_enrollment_bulk_status"),
            {"offering": self.offering_b.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["selected_offering"])
        self.assertNotContains(response, "Form 1 B")

    def test_stream_list_is_limited_to_assigned_campus(self):
        response = self.client.get(reverse("admin_stream_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blue")
        self.assertNotContains(response, "Red")

    def test_report_card_for_other_campus_student_is_not_accessible(self):
        response = self.client.get(
            reverse("admin_report_card_view", args=[self.student_b.pk, self.term.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_term_report_cards_do_not_include_other_campus_learners(self):
        response = self.client.get(reverse("admin_term_report_cards", args=[self.term.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amina")
        self.assertNotContains(response, "Brian")

    def test_stream_promotion_overrides_tampered_session_campus(self):
        session = self.client.session
        session[SESSION_CURRENT_CAMPUS_ID] = self.campus_b.pk
        session.save()

        response = self.client.get(reverse("admin_stream_promotion"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blue")
        self.assertNotContains(response, "Red")
        self.assertEqual(self.client.session[SESSION_CURRENT_CAMPUS_ID], self.campus_a.pk)

    def test_campus_admin_without_assignment_fails_closed(self):
        unassigned = User.objects.create_user(username="unassigned-campus-admin", password="test-pass-123")
        UserRole.objects.create(user=unassigned, role=self.role, campus=None)
        self.client.force_login(unassigned)

        response = self.client.get(reverse("admin_classgroup_list"))

        self.assertEqual(response.status_code, 403)
