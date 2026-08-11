from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.reports.models import TermReportRemark
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Stream
from .reports import ReportCard


class TermReportRemarkTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Remark Test School")
        self.campus_a = Campus.objects.create(
            organization=self.organization,
            name="Campus A",
            code="REMARK-A",
            is_default=True,
        )
        self.campus_b = Campus.objects.create(
            organization=self.organization,
            name="Campus B",
            code="REMARK-B",
        )
        self.year = AcademicYear.objects.create(name="2043")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.course = Course.objects.create(name="Science", code="SCI-2043")

        self.class_a = ClassGroup.objects.create(campus=self.campus_a, name="Form A", code="REMARK-FA")
        self.class_b = ClassGroup.objects.create(campus=self.campus_b, name="Form B", code="REMARK-FB")
        self.stream_a = Stream.objects.create(class_group=self.class_a, name="East", capacity=40)
        self.stream_b = Stream.objects.create(class_group=self.class_b, name="West", capacity=40)
        self.student_a = StudentProfile.objects.create(
            campus=self.campus_a,
            stream=self.stream_a,
            student_id="REMARK-A-001",
            first_name="Alice",
            last_name="Auma",
        )
        self.student_b = StudentProfile.objects.create(
            campus=self.campus_b,
            stream=self.stream_b,
            student_id="REMARK-B-001",
            first_name="Brian",
            last_name="Bukenya",
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
        Enrollment.objects.create(campus=self.campus_a, offering=self.offering_a, student=self.student_a)
        Enrollment.objects.create(campus=self.campus_b, offering=self.offering_b, student=self.student_b)

        self.campus_admin_role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        self.admin_role, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Administrator"},
        )
        self.campus_admin = User.objects.create_user(username="remark-campus-admin", password="test-pass-123")
        UserRole.objects.create(user=self.campus_admin, role=self.campus_admin_role, campus=self.campus_a)
        self.global_admin = User.objects.create_user(username="remark-global-admin", password="test-pass-123")
        UserRole.objects.create(user=self.global_admin, role=self.admin_role, campus=None)

    def test_campus_admin_workspace_only_lists_assigned_campus_learners(self):
        self.client.force_login(self.campus_admin)

        response = self.client.get(reverse("admin_term_report_remarks", args=[self.term.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice")
        self.assertNotContains(response, "Brian")
        self.assertFalse(response.context["can_edit_head"])

    def test_campus_admin_cannot_post_other_campus_learner(self):
        self.client.force_login(self.campus_admin)

        response = self.client.post(
            reverse("admin_term_report_remarks", args=[self.term.pk]),
            {
                "student_ids": [self.student_b.pk],
                f"class_teacher_comment_{self.student_b.pk}": "Forged remote comment",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(TermReportRemark.objects.filter(student=self.student_b, term=self.term).exists())

    def test_campus_admin_can_edit_teacher_remark_but_not_head_remark(self):
        remark = TermReportRemark.objects.create(
            campus=self.campus_a,
            student=self.student_a,
            term=self.term,
            class_teacher_comment="Original teacher comment",
            head_comment="Approved head comment",
        )
        self.client.force_login(self.campus_admin)

        response = self.client.post(
            reverse("admin_term_report_remarks", args=[self.term.pk]),
            {
                "student_ids": [self.student_a.pk],
                f"class_teacher_comment_{self.student_a.pk}": "Updated class teacher comment",
                f"head_comment_{self.student_a.pk}": "FORGED HEAD COMMENT",
            },
        )

        self.assertEqual(response.status_code, 302)
        remark.refresh_from_db()
        self.assertEqual(remark.class_teacher_comment, "Updated class teacher comment")
        self.assertEqual(remark.head_comment, "Approved head comment")
        self.assertEqual(remark.updated_by_id, self.campus_admin.pk)

    def test_global_admin_can_edit_head_remark_for_selected_campus(self):
        self.client.force_login(self.global_admin)

        response = self.client.post(
            reverse("admin_term_report_remarks", args=[self.term.pk]),
            {
                "campus": self.campus_a.pk,
                "student_ids": [self.student_a.pk],
                f"class_teacher_comment_{self.student_a.pk}": "Class teacher summary",
                f"head_comment_{self.student_a.pk}": "Head approves continued progress.",
            },
        )

        self.assertEqual(response.status_code, 302)
        remark = TermReportRemark.objects.get(student=self.student_a, term=self.term)
        self.assertEqual(remark.class_teacher_comment, "Class teacher summary")
        self.assertEqual(remark.head_comment, "Head approves continued progress.")
        self.assertEqual(remark.updated_by_id, self.global_admin.pk)

    def test_report_card_serializes_consolidated_term_remarks(self):
        TermReportRemark.objects.create(
            campus=self.campus_a,
            student=self.student_a,
            term=self.term,
            class_teacher_comment="Steady effort throughout the term.",
            head_comment="Promising progress; keep it up.",
        )

        data = ReportCard(self.student_a.pk, self.term.pk).to_dict()

        self.assertEqual(data["remarks"]["class_teacher_comment"], "Steady effort throughout the term.")
        self.assertEqual(data["remarks"]["head_comment"], "Promising progress; keep it up.")
