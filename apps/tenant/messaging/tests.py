from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.tenant.hr.models import Department, StaffProfile
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Conversation, Message


class ParentMessagingExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = OrganizationProfile.objects.create(name="Messaging School")
        cls.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        cls.other_campus = Campus.objects.create(
            organization=organization,
            name="Other Campus",
            code="OTHER",
        )
        cls.roles = {}
        for code, label in Role.CODE_CHOICES:
            role, _created = Role.objects.get_or_create(
                code=code,
                defaults={"name": label},
            )
            cls.roles[code] = role

        cls.parent_user = cls._user("parent", Role.PARENT)
        parent = ParentProfile.objects.create(
            user=cls.parent_user,
            first_name="Pat",
            last_name="Parent",
        )
        learner = StudentProfile.objects.create(
            campus=cls.campus,
            first_name="Learner",
            last_name="One",
        )
        ParentStudentLink.objects.create(parent=parent, student=learner)

        cls.teacher_user = cls._teacher("teacher", cls.campus)
        cls.other_teacher = cls._teacher("other-teacher", cls.other_campus)
        cls.global_admin = cls._user("global-admin", Role.ADMIN)
        cls.finance_user = cls._finance_user("bursar", cls.campus)
        cls.outside_finance_user = cls._finance_user(
            "outside-bursar",
            cls.other_campus,
        )

        cls.conversation = Conversation.objects.create(
            subject="Invoice support",
            created_by=cls.parent_user,
            campus=cls.campus,
        )
        cls.conversation.participants.add(cls.parent_user, cls.finance_user)
        Message.objects.create(
            conversation=cls.conversation,
            sender=cls.parent_user,
            content="Please help me understand this balance.",
        )

    @classmethod
    def _user(cls, username, role_code, campus=None):
        user = User.objects.create_user(username=username, password="StrongPass123!")
        UserRole.objects.create(
            user=user,
            role=cls.roles[role_code],
            campus=campus,
        )
        return user

    @classmethod
    def _teacher(cls, username, campus):
        user = cls._user(username, Role.TEACHER)
        TeacherProfile.objects.create(
            user=user,
            campus=campus,
            first_name="Test",
            last_name="Teacher",
        )
        return user

    @classmethod
    def _finance_user(cls, username, campus):
        user = cls._user(username, Role.CAMPUS_ADMIN, campus=campus)
        department = Department.objects.create(
            campus=campus,
            name=f"Finance {username}",
            code=username[:8].upper(),
        )
        StaffProfile.objects.create(
            user=user,
            campus=campus,
            first_name="Test",
            last_name="Bursar",
            staff_category=StaffProfile.NON_TEACHING,
            department=department,
        )
        return user

    def setUp(self):
        self.client.force_login(self.parent_user)

    def test_parent_stays_in_parent_shell_across_messaging_pages(self):
        urls = (
            reverse("messaging_inbox"),
            reverse("messaging_conversation_new"),
            reverse(
                "messaging_conversation_detail",
                kwargs={"pk": self.conversation.pk},
            ),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "portals/parent/base.html")
                self.assertTemplateNotUsed(response, "portals/admin/base.html")
                self.assertNotContains(response, "Group Message")

    def test_parent_recipient_list_is_role_and_campus_scoped(self):
        response = self.client.get(reverse("messaging_conversation_new"))
        recipient_ids = set(
            response.context["form"]
            .fields["recipient"]
            .queryset.values_list("pk", flat=True)
        )
        self.assertTrue(
            {self.teacher_user.pk, self.finance_user.pk, self.global_admin.pk}
            <= recipient_ids
        )
        self.assertNotIn(self.other_teacher.pk, recipient_ids)
        self.assertNotIn(self.outside_finance_user.pk, recipient_ids)
        self.assertNotIn(self.parent_user.pk, recipient_ids)

    def test_finance_shortcut_prefills_and_restricts_recipients(self):
        response = self.client.get(
            reverse("messaging_conversation_new")
            + "?topic=finance&invoice=INV-1042"
        )
        self.assertContains(response, "Ask Finance Office")
        self.assertEqual(
            response.context["form"].initial["subject"],
            "Invoice question: INV-1042",
        )
        recipient_ids = set(
            response.context["form"]
            .fields["recipient"]
            .queryset.values_list("pk", flat=True)
        )
        self.assertTrue(
            {self.finance_user.pk, self.global_admin.pk} <= recipient_ids
        )
        self.assertNotIn(self.teacher_user.pk, recipient_ids)
        self.assertNotIn(self.outside_finance_user.pk, recipient_ids)

    def test_tampered_cross_campus_recipient_is_rejected(self):
        response = self.client.post(
            reverse("messaging_conversation_new") + "?topic=finance",
            {
                "subject": "Invoice question",
                "recipient": self.outside_finance_user.pk,
                "content": "Please review the invoice.",
            },
        )
        self.assertIn("recipient", response.context["form"].errors)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_admin_retains_admin_shell_and_bulk_action(self):
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse("messaging_inbox"))
        self.assertTemplateUsed(response, "portals/admin/base.html")
        self.assertContains(response, "Group Message")


class MessagingTemplateContractTests(SimpleTestCase):
    def test_shared_pages_use_dynamic_shell_and_finance_links(self):
        messaging_root = (
            Path(settings.BASE_DIR) / "templates" / "portals" / "messaging"
        )
        for name in ("inbox.html", "conversation_form.html", "conversation_detail.html"):
            content = (messaging_root / name).read_text(encoding="utf-8")
            self.assertIn("{% extends base_template %}", content)
            self.assertNotIn("{% extends 'portals/admin/base.html' %}", content)

        finance_root = (
            Path(settings.BASE_DIR)
            / "templates"
            / "portals"
            / "parent"
            / "finance"
        )
        self.assertIn(
            "?topic=finance",
            (finance_root / "invoices_list.html").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "?topic=finance&amp;invoice=",
            (finance_root / "invoice_detail.html").read_text(encoding="utf-8"),
        )
