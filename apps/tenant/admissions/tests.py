from decimal import Decimal
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization

from .models import AdmissionAppointment, Applicant, ApplicantDocument, ApplicantPayment


class PublicAdmissionsTrackerTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.applicant = Applicant.objects.create(
            first_name="Amina",
            last_name="Tracker",
            email="parent@example.test",
            phone="0772123456",
            campus=self.campus,
            status=Applicant.IN_REVIEW,
            submitted_online=True,
        )

    def test_tracker_shows_documents_interview_decision_and_payment_sections(self):
        ApplicantDocument.objects.create(
            applicant=self.applicant,
            title="Previous report",
            file=SimpleUploadedFile("report.txt", b"report"),
        )
        AdmissionAppointment.objects.create(
            applicant=self.applicant,
            appointment_type=AdmissionAppointment.INTERVIEW,
            status=AdmissionAppointment.SCHEDULED,
            scheduled_at=timezone.now() + timedelta(days=3),
            location="Admissions office",
        )
        ApplicantPayment.objects.create(
            applicant=self.applicant,
            amount=Decimal("25000"),
            method=ApplicantPayment.MOBILE,
            status=ApplicantPayment.PENDING,
            reference="ADM-PAY-1",
        )

        response = self.client.get(
            reverse("public_admissions_track"),
            {"reference": self.applicant.application_reference, "contact": self.applicant.email},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Application timeline")
        self.assertContains(response, "Required documents")
        self.assertContains(response, "Previous report")
        self.assertContains(response, "Interview")
        self.assertContains(response, "Admission decision")
        self.assertContains(response, "Payment instructions")
        self.assertContains(response, "ADM-PAY-1")

    def test_success_page_links_to_tracker(self):
        response = self.client.get(reverse("public_admissions_success", kwargs={"reference": self.applicant.application_reference}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Track application")
        self.assertContains(response, self.applicant.application_reference)
