from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Book, BookCopy, BookLoan, Fine


class LibraryAdminCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Library Campus",
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Reader",
            student_id="LIB-VISIBLE",
            campus=self.campus,
            is_active=True,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Reader",
            student_id="LIB-HIDDEN",
            campus=self.other_campus,
            is_active=True,
        )
        self.book = Book.objects.create(title="Campus Library Book", is_active=True)
        self.copy = BookCopy.objects.create(
            book=self.book,
            copy_code="LIB-COPY-1",
            barcode="LIB-BAR-1",
            status=BookCopy.CHECKED_OUT,
            is_active=True,
        )
        self.hidden_copy = BookCopy.objects.create(
            book=self.book,
            copy_code="LIB-COPY-2",
            barcode="LIB-BAR-2",
            status=BookCopy.CHECKED_OUT,
            is_active=True,
        )
        self.loan = BookLoan.objects.create(
            copy=self.copy,
            borrower_type=BookLoan.BORROWER_TYPE_STUDENT,
            student=self.student,
            due_date=timezone.localdate() + timedelta(days=7),
            status=BookLoan.OPEN,
        )
        self.hidden_loan = BookLoan.objects.create(
            copy=self.hidden_copy,
            borrower_type=BookLoan.BORROWER_TYPE_STUDENT,
            student=self.hidden_student,
            due_date=timezone.localdate() + timedelta(days=7),
            status=BookLoan.OPEN,
        )
        self.fine = Fine.objects.create(
            loan=self.loan,
            borrower_type=Fine.BORROWER_TYPE_STUDENT,
            student=self.student,
            amount=Decimal("10.00"),
            reason="Visible fine",
            status=Fine.UNPAID,
        )
        self.hidden_fine = Fine.objects.create(
            loan=self.hidden_loan,
            borrower_type=Fine.BORROWER_TYPE_STUDENT,
            student=self.hidden_student,
            amount=Decimal("20.00"),
            reason="Hidden fine",
            status=Fine.UNPAID,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="library_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_loan_and_fine_lists_are_scoped(self):
        self.client.login(username="library_campus_admin", password="test-pass-123")

        loans_response = self.client.get(reverse("admin_library_loans_list"))
        fines_response = self.client.get(reverse("admin_library_fines_list"))

        self.assertEqual(loans_response.status_code, 200)
        self.assertContains(loans_response, "LIB-VISIBLE")
        self.assertNotContains(loans_response, "LIB-HIDDEN")
        self.assertEqual(fines_response.status_code, 200)
        fine_ids = {fine.pk for fine in fines_response.context["fines"]}
        self.assertIn(self.fine.pk, fine_ids)
        self.assertNotIn(self.hidden_fine.pk, fine_ids)

    def test_campus_admin_cannot_access_or_return_other_campus_loan(self):
        self.client.login(username="library_campus_admin", password="test-pass-123")

        edit_response = self.client.get(reverse("admin_library_loan_edit", kwargs={"pk": self.hidden_loan.pk}))
        return_response = self.client.post(reverse("admin_library_loan_mark_returned", kwargs={"pk": self.hidden_loan.pk}))

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(return_response.status_code, 404)
        self.hidden_loan.refresh_from_db()
        self.assertEqual(self.hidden_loan.status, BookLoan.OPEN)

    def test_campus_admin_cannot_checkout_to_other_campus_student(self):
        available_copy = BookCopy.objects.create(
            book=self.book,
            copy_code="LIB-COPY-3",
            barcode="LIB-BAR-3",
            status=BookCopy.AVAILABLE,
            is_active=True,
        )
        self.client.login(username="library_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_library_loan_create"),
            {
                "copy": available_copy.pk,
                "borrower_type": BookLoan.BORROWER_TYPE_STUDENT,
                "student": self.hidden_student.pk,
                "staff": "",
                "due_date": (timezone.localdate() + timedelta(days=7)).isoformat(),
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(BookLoan.objects.filter(copy=available_copy, student=self.hidden_student).exists())
        available_copy.refresh_from_db()
        self.assertEqual(available_copy.status, BookCopy.AVAILABLE)

    def test_campus_admin_barcode_checkin_cannot_return_other_campus_loan(self):
        self.client.login(username="library_campus_admin", password="test-pass-123")

        response = self.client.post(reverse("admin_library_checkin"), {"copy_code_or_barcode": self.hidden_copy.barcode})

        self.assertEqual(response.status_code, 200)
        self.hidden_loan.refresh_from_db()
        self.hidden_copy.refresh_from_db()
        self.assertEqual(self.hidden_loan.status, BookLoan.OPEN)
        self.assertEqual(self.hidden_copy.status, BookCopy.CHECKED_OUT)

    def test_campus_admin_cannot_mutate_other_campus_fine(self):
        self.client.login(username="library_campus_admin", password="test-pass-123")

        paid_response = self.client.post(reverse("admin_library_fine_mark_paid", kwargs={"pk": self.hidden_fine.pk}))
        waive_response = self.client.post(reverse("admin_library_fine_waive", kwargs={"pk": self.hidden_fine.pk}))

        self.assertEqual(paid_response.status_code, 404)
        self.assertEqual(waive_response.status_code, 404)
        self.hidden_fine.refresh_from_db()
        self.assertEqual(self.hidden_fine.status, Fine.UNPAID)
