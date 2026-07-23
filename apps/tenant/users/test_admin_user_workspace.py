from django.test import TestCase
from django.urls import reverse

from .models import Role, User


class AdminUserWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_role = Role.objects.create(code=Role.ADMIN, name="Administrator")
        cls.teacher_role = Role.objects.create(code=Role.TEACHER, name="Teacher")
        cls.parent_role = Role.objects.create(code=Role.PARENT, name="Parent")

        cls.admin = User.objects.create_user(
            username="workspace-admin",
            password="StrongPass123!",
            email="workspace-admin@example.com",
        )
        cls.admin.roles.add(cls.admin_role)

        cls.active_teacher = User.objects.create_user(
            username="active-teacher",
            password="StrongPass123!",
            first_name="Active",
            last_name="Teacher",
            email="active-teacher@example.com",
            phone="+256700000101",
        )
        cls.active_teacher.roles.add(cls.teacher_role)

        cls.inactive_teacher = User.objects.create_user(
            username="inactive-teacher",
            password="StrongPass123!",
            first_name="Inactive",
            last_name="Teacher",
            email="inactive-teacher@example.com",
            is_active=False,
        )
        cls.inactive_teacher.roles.add(cls.teacher_role)

        cls.pending_parent = User.objects.create_user(
            username="pending-parent",
            password="StrongPass123!",
            email="pending-parent@example.com",
            must_change_password=True,
        )
        cls.pending_parent.roles.add(cls.parent_role)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_role_and_status_filters_are_combined(self):
        response = self.client.get(
            reverse("admin_users_list"),
            {"role": Role.TEACHER, "status": "active"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "active-teacher")
        self.assertNotContains(response, "inactive-teacher")
        self.assertEqual(response.context["filtered_users_count"], 1)
        self.assertEqual(response.context["selected_role"], Role.TEACHER)
        self.assertEqual(response.context["selected_status"], "active")

    def test_search_includes_phone_numbers(self):
        response = self.client.get(reverse("admin_users_list"), {"q": "700000101"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "active-teacher")
        self.assertNotContains(response, "pending-parent")

    def test_summary_flags_inactive_and_first_login_accounts(self):
        response = self.client.get(reverse("admin_users_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_users_count"], 4)
        self.assertEqual(response.context["active_users_count"], 3)
        self.assertEqual(response.context["needs_attention_count"], 2)

    def test_role_update_replaces_selected_roles_and_confirms_change(self):
        response = self.client.post(
            reverse("admin_users_roles_edit", args=[self.pending_parent.pk]),
            {"role_ids": [self.teacher_role.pk]},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.pending_parent.refresh_from_db()
        self.assertEqual(
            set(self.pending_parent.roles.values_list("code", flat=True)),
            {Role.TEACHER},
        )
        self.assertContains(response, "Access roles for pending-parent were updated.")
