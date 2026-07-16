from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Stream
from apps.tenant.announcements.models import Announcement
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.coursework.models import Assignment
from apps.tenant.finance.models import Invoice, InvoiceLine, OutboundMessageLog
from apps.tenant.orgsettings.models import ActionLog, Campus, Notification
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.digest import DigestWindow, build_parent_digest, send_all_parent_digests, send_parent_digest
from apps.tenant.parents.models import ParentDigest, ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole


class ParentDigestTests(TestCase):
    def setUp(self):
        self.parent_role, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
        self.admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin"})
        self.admin = User.objects.create_user(username="digest_admin", password="test-pass-123")
        self.admin.roles.add(self.admin_role)
        self.user = User.objects.create_user(username="digest_parent", password="test-pass-123")
        self.user.roles.add(self.parent_role)
        self.parent = ParentProfile.objects.create(
            user=self.user,
            first_name="Pat",
            last_name="Digest",
            email="pat@example.test",
        )
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        year = AcademicYear.objects.create(name="2026", is_current=True)
        self.term = AcademicTerm.objects.create(year=year, name="Term 1", order=1, is_current=True)
        class_group = ClassGroup.objects.create(name="Primary 5", campus=self.campus)
        self.stream = Stream.objects.create(class_group=class_group, name="Blue")
        self.course = Course.objects.create(name="Mathematics")
        self.offering = CourseOffering.objects.create(term=self.term, course=self.course, class_group=class_group, campus=self.campus)
        self.student = StudentProfile.objects.create(
            first_name="Ada",
            last_name="Learner",
            stream=self.stream,
            campus=self.campus,
            student_id="ST-001",
        )
        ParentStudentLink.objects.create(parent=self.parent, student=self.student, is_primary=True)
        self.window = DigestWindow(start=date(2026, 7, 6), end=date(2026, 7, 12))

    def test_build_parent_digest_summarizes_linked_child(self):
        session = AttendanceSession.objects.create(offering=self.offering, date=date(2026, 7, 10))
        AttendanceEntry.objects.create(session=session, student=self.student, status=AttendanceEntry.ABSENT)
        invoice = Invoice.objects.create(student=self.student, reference="INV-DIG-1", due_date=date(2026, 7, 8))
        InvoiceLine.objects.create(invoice=invoice, description="Tuition", quantity=1, unit_amount=Decimal("250000"))
        Assignment.objects.create(
            title="Fractions worksheet",
            stream=self.stream,
            due_date=timezone.make_aware(timezone.datetime(2026, 7, 13, 12, 0)),
            is_active=True,
        )
        announcement = Announcement.objects.create(title="Parents meeting", body="Bring report books.", audience=Announcement.PARENTS)
        Announcement.objects.filter(pk=announcement.pk).update(
            created_at=timezone.make_aware(timezone.datetime(2026, 7, 11, 9, 0))
        )

        digest = build_parent_digest(self.parent, window=self.window)

        self.assertEqual(digest["totals"]["children"], 1)
        self.assertEqual(digest["totals"]["absences"], 1)
        self.assertEqual(digest["totals"]["due_assignments"], 1)
        self.assertEqual(digest["totals"]["balance"], Decimal("250000"))
        self.assertIn("Ada Learner", digest["message"])
        self.assertIn("Parents meeting", digest["message"])

    def test_send_parent_digest_creates_notification_and_pushes(self):
        with mock.patch("apps.tenant.parents.digest.send_web_push_to_user") as push:
            push.return_value = {"sent": 1, "attempted": 1, "results": [{"ok": True}]}
            result = send_parent_digest(self.parent, window=self.window)

        self.assertTrue(result["sent"])
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
        self.assertEqual(ParentDigest.objects.filter(parent=self.parent, status=ParentDigest.SENT).count(), 1)
        self.assertEqual(ActionLog.objects.filter(action="PARENT_DIGEST_SENT").count(), 1)
        push.assert_called_once()

    def test_send_parent_digest_blocks_duplicate_window_without_force(self):
        first = send_parent_digest(self.parent, window=self.window, include_push=False)
        second = send_parent_digest(self.parent, window=self.window, include_push=False)

        self.assertTrue(first["sent"])
        self.assertFalse(second["sent"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(ParentDigest.objects.filter(parent=self.parent).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)

    def test_send_parent_digest_force_resends_existing_window(self):
        send_parent_digest(self.parent, window=self.window, include_push=False)
        result = send_parent_digest(self.parent, window=self.window, include_push=False, force=True)

        self.assertTrue(result["sent"])
        self.assertEqual(ParentDigest.objects.filter(parent=self.parent).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 2)

    def test_send_parent_digest_can_email_parent_with_html_alternative(self):
        with mock.patch("apps.tenant.parents.digest.EmailMultiAlternatives") as email_cls:
            email_obj = email_cls.return_value
            email_obj.send.return_value = 1
            result = send_parent_digest(
                self.parent,
                window=self.window,
                include_push=False,
                include_email=True,
            )

        self.assertTrue(result["email"]["sent"])
        email_cls.assert_called_once()
        self.assertEqual(email_cls.call_args.args[3], ["pat@example.test"])
        email_obj.attach_alternative.assert_called_once()
        self.assertIn("text/html", email_obj.attach_alternative.call_args.args)

    def test_send_parent_digest_reports_missing_email(self):
        self.parent.email = ""
        self.parent.user.email = ""
        self.parent.user.save(update_fields=["email"])
        self.parent.save(update_fields=["email"])

        result = send_parent_digest(
            self.parent,
            window=self.window,
            include_push=False,
            include_email=True,
        )

        self.assertFalse(result["email"]["sent"])
        self.assertEqual(result["email"]["reason"], "Parent has no email address.")

    def test_send_parent_digest_can_log_whatsapp_dry_run(self):
        self.parent.phone = "0772 123 456"
        self.parent.allow_whatsapp_alerts = True
        self.parent.save(update_fields=["phone", "allow_whatsapp_alerts"])

        result = send_parent_digest(
            self.parent,
            window=self.window,
            include_push=False,
            include_whatsapp=True,
            whatsapp_dry_run=True,
        )

        self.assertTrue(result["sent"])
        self.assertTrue(result["whatsapp"]["attempted"])
        self.assertEqual(result["whatsapp"]["status"], "dry_run")
        log = OutboundMessageLog.objects.get(message_type=OutboundMessageLog.PARENT_DIGEST)
        self.assertEqual(log.channel, OutboundMessageLog.WHATSAPP)
        self.assertEqual(log.status, OutboundMessageLog.DRY_RUN)

    def test_send_all_parent_digests_uses_parent_preferences(self):
        self.parent.digest_pwa_enabled = False
        self.parent.digest_email_enabled = True
        self.parent.digest_whatsapp_enabled = True
        self.parent.phone = "0772 123 456"
        self.parent.save(
            update_fields=[
                "digest_pwa_enabled",
                "digest_email_enabled",
                "digest_whatsapp_enabled",
                "phone",
            ]
        )

        with mock.patch("apps.tenant.parents.digest.EmailMultiAlternatives") as email_cls:
            email_cls.return_value.send.return_value = 1
            result = send_all_parent_digests(
                window=self.window,
                include_push=False,
                include_email=False,
                include_whatsapp=False,
                whatsapp_dry_run=True,
                use_parent_preferences=True,
            )

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["push_sent"], 0)
        self.assertEqual(result["email_sent"], 1)
        self.assertEqual(result["whatsapp_sent"], 0)
        self.assertEqual(OutboundMessageLog.objects.filter(message_type=OutboundMessageLog.PARENT_DIGEST).count(), 1)

    def test_send_all_parent_digests_skips_disabled_digest_preference(self):
        self.parent.digest_enabled = False
        self.parent.save(update_fields=["digest_enabled"])

        result = send_all_parent_digests(window=self.window, use_parent_preferences=True)

        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped"], 1)
        digest = ParentDigest.objects.get(parent=self.parent)
        self.assertEqual(digest.status, ParentDigest.SKIPPED)

    def test_send_parent_digest_skips_parent_without_user(self):
        parent = ParentProfile.objects.create(first_name="No", last_name="Login")

        result = send_parent_digest(parent, window=self.window)

        self.assertFalse(result["sent"])
        self.assertIn("no linked user", result["reason"].lower())
        self.assertEqual(ActionLog.objects.filter(action="PARENT_DIGEST_SKIPPED").count(), 1)

    def test_admin_digest_preview_renders_recent_activity(self):
        send_parent_digest(self.parent, window=self.window, created_by=self.admin, include_push=False)
        self.client.login(username="digest_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_parents_digest", kwargs={"pk": self.parent.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent digest activity")
        self.assertContains(response, "PARENT_DIGEST_SENT")

    def test_parent_registry_links_digest_preview(self):
        self.client.login(username="digest_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_parents_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin_parents_digest", kwargs={"pk": self.parent.pk}))
        self.assertContains(response, reverse("admin_parents_digest_send_all"))
        self.assertContains(response, "Send Digests")
        self.assertContains(response, "Digest")

    def test_parent_digest_history_renders_sent_digest(self):
        send_parent_digest(self.parent, window=self.window, include_push=False)
        self.client.login(username="digest_parent", password="test-pass-123")

        response = self.client.get(reverse("parent_digest_history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly parent digests")
        self.assertContains(response, "Weekly parent digest")

    def test_campus_admin_cannot_preview_other_campus_parent_digest(self):
        other_campus = Campus.objects.create(
            organization=self.campus.organization,
            name="Digest Other Campus",
            is_active=True,
        )
        other_user = User.objects.create_user(username="digest_other_parent", password="test-pass-123")
        other_user.roles.add(self.parent_role)
        other_parent = ParentProfile.objects.create(user=other_user, first_name="Other", last_name="Parent")
        other_student = StudentProfile.objects.create(
            first_name="Other",
            last_name="Learner",
            campus=other_campus,
            student_id="ST-OTHER",
        )
        ParentStudentLink.objects.create(parent=other_parent, student=other_student)

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        campus_admin = User.objects.create_user(username="digest_campus_admin", password="test-pass-123")
        campus_admin.roles.add(campus_role)
        UserRole.objects.create(user=campus_admin, role=campus_role, campus=self.campus)

        self.client.login(username="digest_campus_admin", password="test-pass-123")
        response = self.client.get(reverse("admin_parents_digest", kwargs={"pk": other_parent.pk}))

        self.assertEqual(response.status_code, 404)

    def test_campus_admin_send_all_digests_only_sends_accessible_campus(self):
        other_campus = Campus.objects.create(
            organization=self.campus.organization,
            name="Digest Bulk Other Campus",
            is_active=True,
        )
        other_user = User.objects.create_user(username="digest_bulk_other_parent", password="test-pass-123")
        other_user.roles.add(self.parent_role)
        other_parent = ParentProfile.objects.create(user=other_user, first_name="Bulk", last_name="Other")
        other_student = StudentProfile.objects.create(
            first_name="Bulk",
            last_name="Other",
            campus=other_campus,
            student_id="ST-BULK-OTHER",
        )
        ParentStudentLink.objects.create(parent=other_parent, student=other_student)

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        campus_admin = User.objects.create_user(username="digest_bulk_campus_admin", password="test-pass-123")
        campus_admin.roles.add(campus_role)
        UserRole.objects.create(user=campus_admin, role=campus_role, campus=self.campus)

        self.client.login(username="digest_bulk_campus_admin", password="test-pass-123")
        response = self.client.post(reverse("admin_parents_digest_send_all"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ParentDigest.objects.filter(parent=self.parent, status=ParentDigest.SENT).exists())
        self.assertFalse(ParentDigest.objects.filter(parent=other_parent).exists())
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
        self.assertFalse(Notification.objects.filter(recipient=other_user).exists())

    def test_campus_admin_parent_registry_hides_other_campus_parent(self):
        other_campus = Campus.objects.create(
            organization=self.campus.organization,
            name="Registry Other Campus",
            is_active=True,
        )
        other_parent = ParentProfile.objects.create(first_name="Registry", last_name="Other")
        other_student = StudentProfile.objects.create(
            first_name="Registry",
            last_name="Learner",
            campus=other_campus,
            student_id="ST-REG-OTHER",
        )
        ParentStudentLink.objects.create(parent=other_parent, student=other_student)

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        campus_admin = User.objects.create_user(username="digest_registry_campus_admin", password="test-pass-123")
        campus_admin.roles.add(campus_role)
        UserRole.objects.create(user=campus_admin, role=campus_role, campus=self.campus)

        self.client.login(username="digest_registry_campus_admin", password="test-pass-123")
        list_response = self.client.get(reverse("admin_parents_list"))
        edit_response = self.client.get(reverse("admin_parents_edit", kwargs={"pk": other_parent.pk}))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Digest, Pat")
        self.assertNotContains(list_response, "Other, Registry")
        self.assertEqual(edit_response.status_code, 404)

    def test_campus_admin_cannot_link_parent_to_other_campus_student(self):
        other_campus = Campus.objects.create(
            organization=self.campus.organization,
            name="Link Other Campus",
            is_active=True,
        )
        other_student = StudentProfile.objects.create(
            first_name="Link",
            last_name="Other",
            campus=other_campus,
            student_id="ST-LINK-OTHER",
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        campus_admin = User.objects.create_user(username="digest_link_campus_admin", password="test-pass-123")
        campus_admin.roles.add(campus_role)
        UserRole.objects.create(user=campus_admin, role=campus_role, campus=self.campus)

        self.client.login(username="digest_link_campus_admin", password="test-pass-123")
        response = self.client.post(
            reverse("admin_parents_add_student", kwargs={"pk": self.parent.pk}),
            {"student": other_student.pk, "relationship": "guardian", "is_primary": "on"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ParentStudentLink.objects.filter(parent=self.parent, student=other_student).exists())
