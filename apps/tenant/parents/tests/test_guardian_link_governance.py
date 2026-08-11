from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.tenant.orgsettings.models import ActionLog
from apps.tenant.parents.link_services import remove_guardian_link, save_guardian_link
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import User


class ParentIdentitySyncTests(TestCase):
    def test_parent_profile_updates_linked_login_identity(self):
        user = User.objects.create_user(
            username="parent-one",
            email="old@example.com",
            first_name="Old",
            last_name="Name",
        )
        parent = ParentProfile.objects.create(
            user=user,
            first_name="Grace",
            last_name="Nabirye",
            phone="0772000000",
            email="grace@example.com",
        )

        user.refresh_from_db()
        self.assertEqual(user.first_name, "Grace")
        self.assertEqual(user.last_name, "Nabirye")
        self.assertEqual(user.phone, "0772000000")
        self.assertEqual(user.email, "grace@example.com")
        self.assertEqual(parent.get_full_name(), "Grace Nabirye")

    def test_parent_profile_does_not_take_email_from_another_user(self):
        User.objects.create_user(username="owner", email="shared@example.com")
        linked_user = User.objects.create_user(username="parent-two", email="safe@example.com")
        parent = ParentProfile.objects.create(
            user=linked_user,
            first_name="John",
            last_name="Kato",
            email="safe@example.com",
        )

        parent.first_name = "Jonathan"
        parent.phone = "0700000000"
        parent.email = "shared@example.com"
        parent.save()

        linked_user.refresh_from_db()
        self.assertEqual(linked_user.first_name, "Jonathan")
        self.assertEqual(linked_user.phone, "0700000000")
        self.assertEqual(linked_user.email, "safe@example.com")


class GuardianLinkGovernanceTests(TestCase):
    def setUp(self):
        self.student = StudentProfile.objects.create(
            student_id="ST-001",
            first_name="Amina",
            last_name="Nansubuga",
        )
        self.first_parent = ParentProfile.objects.create(first_name="Sarah", last_name="Nansubuga")
        self.second_parent = ParentProfile.objects.create(first_name="Peter", last_name="Nansubuga")

    def test_new_primary_guardian_demotes_previous_primary(self):
        first_link, created, demoted = save_guardian_link(
            parent=self.first_parent,
            student=self.student,
            relationship="Mother",
            is_primary=True,
        )
        self.assertTrue(created)
        self.assertEqual(demoted, 0)
        self.assertTrue(first_link.is_primary)

        second_link, created, demoted = save_guardian_link(
            parent=self.second_parent,
            student=self.student,
            relationship="Father",
            is_primary=True,
        )

        first_link.refresh_from_db()
        self.assertTrue(created)
        self.assertEqual(demoted, 1)
        self.assertFalse(first_link.is_primary)
        self.assertTrue(second_link.is_primary)
        self.assertEqual(
            ParentStudentLink.objects.filter(student=self.student, is_primary=True).count(),
            1,
        )

    def test_link_update_is_idempotent_and_audited_on_both_records(self):
        link, created, _ = save_guardian_link(
            parent=self.first_parent,
            student=self.student,
            relationship="Guardian",
            is_primary=False,
        )
        self.assertTrue(created)

        same_link, created, _ = save_guardian_link(
            parent=self.first_parent,
            student=self.student,
            relationship="Mother",
            is_primary=True,
        )
        self.assertFalse(created)
        self.assertEqual(link.pk, same_link.pk)
        self.assertEqual(ParentStudentLink.objects.filter(parent=self.first_parent, student=self.student).count(), 1)

        parent_ct = ContentType.objects.get_for_model(self.first_parent)
        student_ct = ContentType.objects.get_for_model(self.student)
        self.assertTrue(
            ActionLog.objects.filter(
                content_type=parent_ct,
                object_id=self.first_parent.pk,
                action="STUDENT_LINK_UPDATED",
            ).exists()
        )
        self.assertTrue(
            ActionLog.objects.filter(
                content_type=student_ct,
                object_id=self.student.pk,
                action="GUARDIAN_LINK_UPDATED",
            ).exists()
        )

    def test_unlink_removes_relationship_and_preserves_audit_event(self):
        link, _, _ = save_guardian_link(
            parent=self.first_parent,
            student=self.student,
            relationship="Mother",
            is_primary=True,
        )
        link_pk = link.pk

        remove_guardian_link(link=link)

        self.assertFalse(ParentStudentLink.objects.filter(pk=link_pk).exists())
        parent_ct = ContentType.objects.get_for_model(self.first_parent)
        student_ct = ContentType.objects.get_for_model(self.student)
        self.assertTrue(
            ActionLog.objects.filter(
                content_type=parent_ct,
                object_id=self.first_parent.pk,
                action="STUDENT_UNLINKED",
            ).exists()
        )
        self.assertTrue(
            ActionLog.objects.filter(
                content_type=student_ct,
                object_id=self.student.pk,
                action="GUARDIAN_UNLINKED",
            ).exists()
        )
