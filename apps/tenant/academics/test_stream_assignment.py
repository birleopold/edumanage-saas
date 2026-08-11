from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import ActionLog, Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import User

from .models import ClassGroup, Stream


class BulkStreamAssignmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="stream-admin",
            email="stream-admin@example.com",
            password="test-pass-123",
        )
        self.client.force_login(self.user)

        self.organization = OrganizationProfile.objects.create(name="Test School")
        self.campus = Campus.objects.create(organization=self.organization, name="Main Campus", code="MAIN")
        self.other_campus = Campus.objects.create(organization=self.organization, name="Other Campus", code="OTHER")

        self.class_group = ClassGroup.objects.create(name="Form 1", code="F1", campus=self.campus)
        self.other_class = ClassGroup.objects.create(name="Form 2", code="F2", campus=self.campus)
        self.remote_class = ClassGroup.objects.create(name="Form 1 Remote", code="F1R", campus=self.other_campus)

        self.stream_a = Stream.objects.create(class_group=self.class_group, name="A", capacity=2)
        self.stream_b = Stream.objects.create(class_group=self.class_group, name="B", capacity=10)
        self.other_class_stream = Stream.objects.create(class_group=self.other_class, name="A", capacity=10)
        self.remote_stream = Stream.objects.create(class_group=self.remote_class, name="A", capacity=10)

        self.unassigned = StudentProfile.objects.create(
            student_id="ST-001",
            first_name="Amina",
            last_name="Nabirye",
            campus=self.campus,
        )
        self.sibling_stream_student = StudentProfile.objects.create(
            student_id="ST-002",
            first_name="Peter",
            last_name="Kato",
            campus=self.campus,
            stream=self.stream_b,
        )
        self.other_class_student = StudentProfile.objects.create(
            student_id="ST-003",
            first_name="Sarah",
            last_name="Namata",
            campus=self.campus,
            stream=self.other_class_stream,
        )
        self.other_campus_student = StudentProfile.objects.create(
            student_id="ST-004",
            first_name="David",
            last_name="Okello",
            campus=self.other_campus,
            stream=self.remote_stream,
        )

    def assignment_url(self):
        return reverse("admin_stream_bulk_assignment")

    def test_workspace_only_lists_same_class_or_unassigned_learners(self):
        response = self.client.get(self.assignment_url(), {"stream": self.stream_a.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amina Nabirye")
        self.assertContains(response, "Peter Kato")
        self.assertNotContains(response, "Sarah Namata")
        self.assertNotContains(response, "David Okello")

    def test_bulk_assignment_moves_eligible_learners_and_audits_each_change(self):
        response = self.client.post(
            self.assignment_url(),
            {
                "stream": self.stream_a.pk,
                "student_ids": [self.unassigned.pk, self.sibling_stream_student.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.unassigned.refresh_from_db()
        self.sibling_stream_student.refresh_from_db()
        self.assertEqual(self.unassigned.stream_id, self.stream_a.pk)
        self.assertEqual(self.sibling_stream_student.stream_id, self.stream_a.pk)

        student_ct = ContentType.objects.get_for_model(StudentProfile)
        self.assertTrue(
            ActionLog.objects.filter(
                content_type=student_ct,
                object_id=self.unassigned.pk,
                action="STREAM_ASSIGNED",
            ).exists()
        )
        self.assertTrue(
            ActionLog.objects.filter(
                content_type=student_ct,
                object_id=self.sibling_stream_student.pk,
                action="STREAM_CHANGED",
            ).exists()
        )

    def test_over_capacity_assignment_is_all_or_nothing(self):
        self.stream_a.capacity = 1
        self.stream_a.save(update_fields=["capacity"])

        response = self.client.post(
            self.assignment_url(),
            {
                "stream": self.stream_a.pk,
                "student_ids": [self.unassigned.pk, self.sibling_stream_student.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.unassigned.refresh_from_db()
        self.sibling_stream_student.refresh_from_db()
        self.assertIsNone(self.unassigned.stream_id)
        self.assertEqual(self.sibling_stream_student.stream_id, self.stream_b.pk)

    def test_crafted_cross_class_selection_is_rejected_without_changes(self):
        response = self.client.post(
            self.assignment_url(),
            {
                "stream": self.stream_a.pk,
                "student_ids": [self.unassigned.pk, self.other_class_student.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.unassigned.refresh_from_db()
        self.other_class_student.refresh_from_db()
        self.assertIsNone(self.unassigned.stream_id)
        self.assertEqual(self.other_class_student.stream_id, self.other_class_stream.pk)

    def test_already_assigned_student_does_not_consume_an_extra_place(self):
        self.unassigned.stream = self.stream_a
        self.unassigned.save(update_fields=["stream"])
        self.stream_a.capacity = 2
        self.stream_a.save(update_fields=["capacity"])

        response = self.client.post(
            self.assignment_url(),
            {
                "stream": self.stream_a.pk,
                "student_ids": [self.unassigned.pk, self.sibling_stream_student.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.sibling_stream_student.refresh_from_db()
        self.assertEqual(self.sibling_stream_student.stream_id, self.stream_a.pk)
        self.assertEqual(
            StudentProfile.objects.filter(stream=self.stream_a, is_active=True).count(),
            2,
        )
