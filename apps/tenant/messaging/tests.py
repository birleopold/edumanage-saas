from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.tenant.hr.models import Department, Position, StaffProfile
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Conversation, Message


class ParentMessagingExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = OrganizationProfile.objects.create(name="Messaging School")
        cls.campus = Campus.objects.create(
            organization=cls.organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        cls.other_campus = Campus.objects.create(
            organization=cls.organization,
            name="Other Campus",
            code="OTHER",
        )
        cls.roles = {
            code: Role.objects.create(code=code, name=label)
            for code, label in Role.CODE_CHOICES
        }

        cls.parent_user = cls._user("parent", Role.PARENT)
        cls.parent_profile = ParentProfile.objects.create(
            user=cls.parent_user,
            first_name="Pat",
            last_name="Parent",
        )
        cls.student = StudentProfile.objects.create(
            campus=cls.campus,
            first_name="Learner",
            last_name="One",
            student_id="ST-001",
        )
        ParentStudentLink.objects.create(
            parent=cls.parent_profile,
            student=cls.student,
            is_primary=True,
        )

        cls.teacher_user = cls._user("teacher", Role.TEACHER)
        TeacherProfile.objects.create(
            user=cls.teacher_user,
            campus=cls.campus,
            first_name="Tina",
            last_name="Teacher",
        )
        cls.other_teacher = cls._user("other-teacher", Role.TEACHER)
        TeacherProfile.objects.create(
            user=cls.other_teacher,
            campus=cls.other_campus,
            first_name="Other",
            last_name="Teacher",
        )

        cls.global_admin = cls._user("global-admin", Role.ADMIN)
        cls.finance_user = cls._user(
            "bursar",
            Role.CAMPUS_ADMIN,
            campus=cls.campus,
        )
        finance_department = Department.objects.create(
            campus=cls.campus,
            name="Finance and Accounts",
            code="FIN",
        )
        bursar_position = Position.objects.create(
            department=finance_department,
            title="School Bursar",
        )
        StaffProfile.objects.create(
            user=cls.finance_user,
            campus=cls.campus,
            first_name="Faith",
            last_name="Bursar",
            staff_category=StaffProfile.NON_TEACHING,
            department=finance_department,
            position=bursar_position,
        )

        cls.outside_finance_user = cls._user(
            "outside-bursar",
            Role.CAMPUS_ADMIN,
            campus=cls.other_campus,
        )
        outside_department = Department.objects.create(
            campus=cls.other_campus,
            name="Finance",
            code="FIN-2",
        )
        StaffProfile.objects.create(
            user=cls.outside_finance_user,
            campus=cls.other_campus,
            first_name="Outside",
            last_name="Bursar",
            staff_category=StaffProfile.NON_TEACHING,
            department=outside_department,
        )

        cls.other_parent_user = cls._user("other-parent", Role.PARENT)
        other_parent = ParentProfile.objects.create(
            user=cls.other_parent_user,
            first_name="Other",
            last_name="Parent",
        )
        ParentStudentLink.objects.create(
            parent=other_parent,
            student=cls.student,
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
        user = User.objects.create_user(
            username=username,
            password="StrongPass123!",
            first_name=username.replace("-", " ").title(),
        )
        UserRole.objects.create(
            user=user,
            role=cls.roles[role_code],
            campus=campus,
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
                self.assertNotTemplateUsed(response, "portals/admin/base.html")
                self.assertNotContains(response, "Group Message")

    def test_parent_general_recipient_list_is_role_and_campus_scoped(self):
        response = self.client.get(reverse("messaging_conversation_new"))
        recipient_ids = set(
            response.context["form"]
            .fields["recipient"]
            .queryset.values_list("pk", flat=True)
        )
        self.assertIn(self.teacher_user.pk, recipient_ids)
        self.assertIn(self.finance_user.pk, recipient_ids)
        self.assertIn(self.global_admin.pk, recipient_ids)
        self.assertNotIn(self.other_teacher.pk, recipient_ids)
        self.assertNotIn(self.outside_finance_user.pk, recipient_ids)
        self.assertNotIn(self.other_parent_user.pk, recipient_ids)
        self.assertNotIn(self.parent_user.pk, recipient_ids)

    def test_finance_shortcut_prefills_subject_and_limits_recipients(self):
        target = reverse("messaging_conversation_new") + "?topic=finance&invoice=INV-1042"
        response = self.client.get(target)
        self.assertEqual(response.status_code, 200)
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
        self.assertIn(self.finance_user.pk, recipient_ids)
        self.assertIn(self.global_admin.pk, recipient_ids)
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
        self.assertEqual(response.status_code, 200)
        self.assertIn("recipient", response.context["form"].errors)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_admin_keeps_admin_shell_and_bulk_action(self):
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse("messaging_inbox"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portals/admin/base.html")
        self.assertContains(response, "Group Message")


class MessagingTemplateContractTests(SimpleTestCase):
    def test_shared_messaging_templates_use_dynamic_role_shell(self):
        root = Path(settings.BASE_DIR) / "templates" / "portals" / "messaging"
        for name in ("inbox.html", "conversation_form.html", "conversation_detail.html"):
            content = (root / name).read_text(encoding="utf-8")
            self.assertIn("{% extends base_template %}", content)
            self.assertNotIn("{% extends 'portals/admin/base.html' %}", content)

    def test_parent_invoice_actions_open_finance_scoped_composer(self):
        root = Path(settings.BASE_DIR) / "templates" / "portals" / "parent" / "finance"
        self.assertIn(
            "?topic=finance",
            (root / "invoices_list.html").read_text(encoding="utf-8"),
        )
        detail = (root / "invoice_detail.html").read_text(encoding="utf-8")
        self.assertIn("?topic=finance&amp;invoice=", detail)
