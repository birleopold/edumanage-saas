from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User

from .models import Campus, Notification, OrganizationProfile
from .notification_forms import NotificationComposerForm
from .notification_state import (
    is_safe_notification_link,
    mark_all_notifications_read,
    mark_notification_read,
    safe_notification_target,
    with_user_read_state,
)
from .notification_views import _users_for_campus


class NotificationReadStateTests(TestCase):
    def setUp(self):
        self.first_user = User.objects.create_user(
            username="notification-user-one",
            password="not-used",
        )
        self.second_user = User.objects.create_user(
            username="notification-user-two",
            password="not-used",
        )
        self.shared = Notification.objects.create(
            recipient=None,
            audience=Notification.ALL,
            title="Shared notice",
            message="Visible to more than one account.",
        )

    def _read_state(self, user, notification=None):
        notification = notification or self.shared
        return with_user_read_state(
            Notification.objects.filter(pk=notification.pk),
            user,
        ).get().user_is_read

    def test_shared_notification_read_state_is_personal(self):
        self.assertFalse(self._read_state(self.first_user))
        self.assertFalse(self._read_state(self.second_user))

        created = mark_notification_read(self.shared, self.first_user)

        self.assertTrue(created)
        self.assertTrue(self._read_state(self.first_user))
        self.assertFalse(self._read_state(self.second_user))
        self.shared.refresh_from_db()
        self.assertFalse(self.shared.is_read)

    def test_direct_notification_keeps_existing_personal_fields(self):
        direct = Notification.objects.create(
            recipient=self.first_user,
            title="Direct notice",
            message="For one account.",
        )

        changed = mark_notification_read(direct, self.first_user)

        self.assertTrue(changed)
        direct.refresh_from_db()
        self.assertTrue(direct.is_read)
        self.assertIsNotNone(direct.read_at)
        self.assertTrue(self._read_state(self.first_user, direct))

    def test_mark_all_does_not_change_another_users_state(self):
        direct = Notification.objects.create(
            recipient=self.first_user,
            title="Direct unread",
            message="One direct item.",
        )

        updated = mark_all_notifications_read(
            Notification.objects.filter(pk__in=[self.shared.pk, direct.pk]),
            self.first_user,
        )

        self.assertEqual(updated, 2)
        self.assertTrue(self._read_state(self.first_user))
        self.assertFalse(self._read_state(self.second_user))
        direct.refresh_from_db()
        self.assertTrue(direct.is_read)


class NotificationLinkSafetyTests(TestCase):
    def test_only_same_site_absolute_paths_are_accepted(self):
        self.assertTrue(is_safe_notification_link("/student/finance/?term=1"))
        self.assertTrue(is_safe_notification_link(""))
        self.assertFalse(is_safe_notification_link("//malicious.example/collect"))
        self.assertFalse(is_safe_notification_link("https://malicious.example/collect"))
        self.assertFalse(is_safe_notification_link("/safe\\malicious.example"))
        self.assertEqual(
            safe_notification_target("//malicious.example/collect"),
            "notifications_list",
        )

    def test_composer_rejects_protocol_relative_link(self):
        form = NotificationComposerForm(
            data={
                "notification_type": "SYSTEM_NOTICE",
                "title": "Unsafe link test",
                "message": "This must stay inside the school portal.",
                "priority": Notification.NORMAL,
                "audience": Notification.ALL,
                "link": "//malicious.example/collect",
            },
            campus_queryset=Campus.objects.none(),
            user_queryset=User.objects.none(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("same-school portal path", form.errors["link"][0])

    def test_legacy_unsafe_link_falls_back_to_notification_inbox(self):
        user = User.objects.create_user(
            username="safe-redirect-student",
            password="safe-password",
        )
        role, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        user.roles.add(role)
        notification = Notification.objects.create(
            recipient=user,
            title="Imported legacy notice",
            message="Contains an unsafe legacy target.",
            link="//malicious.example/collect",
        )
        self.client.force_login(user)

        original_schema_name = getattr(connection, "schema_name", None)
        connection.schema_name = "public"
        try:
            response = self.client.get(
                reverse("notifications_read", args=[notification.pk])
            )
        finally:
            if original_schema_name is None:
                try:
                    del connection.schema_name
                except AttributeError:
                    pass
            else:
                connection.schema_name = original_schema_name

        self.assertRedirects(
            response,
            reverse("notifications_list"),
            fetch_redirect_response=False,
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)


class CampusNotificationTargetingTests(TestCase):
    def setUp(self):
        organization = OrganizationProfile.objects.create(name="Targeting School")
        self.first_campus = Campus.objects.create(
            organization=organization,
            name="North Campus",
            code="NORTH",
        )
        self.second_campus = Campus.objects.create(
            organization=organization,
            name="South Campus",
            code="SOUTH",
        )

    def test_authoritative_profiles_drive_campus_membership(self):
        north_student_user = User.objects.create_user(username="north-student")
        south_student_user = User.objects.create_user(username="south-student")
        north_teacher_user = User.objects.create_user(username="north-teacher")
        north_parent_user = User.objects.create_user(username="north-parent")

        north_student = StudentProfile.objects.create(
            user=north_student_user,
            campus=self.first_campus,
            first_name="North",
            last_name="Student",
        )
        StudentProfile.objects.create(
            user=south_student_user,
            campus=self.second_campus,
            first_name="South",
            last_name="Student",
        )
        TeacherProfile.objects.create(
            user=north_teacher_user,
            campus=self.first_campus,
            first_name="North",
            last_name="Teacher",
        )
        parent = ParentProfile.objects.create(
            user=north_parent_user,
            first_name="North",
            last_name="Parent",
        )
        ParentStudentLink.objects.create(
            parent=parent,
            student=north_student,
            relationship="Guardian",
            is_primary=True,
        )

        targeted_ids = set(
            _users_for_campus(User.objects.all(), self.first_campus).values_list(
                "pk",
                flat=True,
            )
        )

        self.assertIn(north_student_user.pk, targeted_ids)
        self.assertIn(north_teacher_user.pk, targeted_ids)
        self.assertIn(north_parent_user.pk, targeted_ids)
        self.assertNotIn(south_student_user.pk, targeted_ids)
