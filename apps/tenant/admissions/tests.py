from decimal import Decimal
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import Role, User, UserRole

from .models import AdmissionAppointment, AdmissionFormTemplate, AdmissionLead, Applicant, ApplicantDocument, ApplicantPayment


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


class AdmissionsAdminCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Admissions Campus",
            is_active=True,
        )
        self.applicant = Applicant.objects.create(
            first_name="Visible",
            last_name="Applicant",
            phone="0700000001",
            campus=self.campus,
            status=Applicant.NEW,
        )
        self.hidden_applicant = Applicant.objects.create(
            first_name="Hidden",
            last_name="Applicant",
            phone="0700000002",
            campus=self.other_campus,
            status=Applicant.NEW,
        )
        self.unassigned_applicant = Applicant.objects.create(
            first_name="Unassigned",
            last_name="Applicant",
            phone="0700000003",
            campus=None,
            status=Applicant.NEW,
        )
        self.lead = AdmissionLead.objects.create(
            learner_name="Visible Lead",
            phone="0710000001",
            campus=self.campus,
        )
        self.hidden_lead = AdmissionLead.objects.create(
            learner_name="Hidden Lead",
            phone="0710000002",
            campus=self.other_campus,
        )
        self.template = AdmissionFormTemplate.objects.create(
            name="Visible Template",
            campus=self.campus,
        )
        self.hidden_template = AdmissionFormTemplate.objects.create(
            name="Hidden Template",
            campus=self.other_campus,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="admissions_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_applicant_list_ignores_forged_campus_filter(self):
        self.client.login(username="admissions_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_admissions_applicants"), {"campus": self.other_campus.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible")
        self.assertContains(response, "Unassigned")
        self.assertNotContains(response, "Hidden")

    def test_campus_admin_cannot_access_other_campus_applicant_actions(self):
        self.client.login(username="admissions_campus_admin", password="test-pass-123")

        detail_response = self.client.get(reverse("admin_admissions_applicant_detail", kwargs={"pk": self.hidden_applicant.pk}))
        edit_response = self.client.get(reverse("admin_admissions_applicant_edit", kwargs={"pk": self.hidden_applicant.pk}))
        status_response = self.client.post(
            reverse("admin_admissions_applicant_set_status", kwargs={"pk": self.hidden_applicant.pk}),
            {"status": Applicant.IN_REVIEW, "note": ""},
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(status_response.status_code, 404)

    def test_campus_admin_cannot_create_or_move_applicant_to_other_campus(self):
        self.client.login(username="admissions_campus_admin", password="test-pass-123")

        create_response = self.client.post(
            reverse("admin_admissions_applicant_create"),
            {
                "campus": self.other_campus.pk,
                "first_name": "Forged",
                "last_name": "Applicant",
                "phone": "0720000001",
                "status": Applicant.NEW,
                "source": Applicant.SOURCE_ADMIN,
            },
        )
        edit_response = self.client.post(
            reverse("admin_admissions_applicant_edit", kwargs={"pk": self.applicant.pk}),
            {
                "campus": self.other_campus.pk,
                "first_name": self.applicant.first_name,
                "last_name": self.applicant.last_name,
                "phone": self.applicant.phone,
                "status": self.applicant.status,
                "source": self.applicant.source,
            },
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 200)
        self.assertFalse(Applicant.objects.filter(first_name="Forged", last_name="Applicant").exists())
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.campus, self.campus)

    def test_campus_admin_leads_are_scoped_and_unassigned_conversion_is_claimed(self):
        self.client.login(username="admissions_campus_admin", password="test-pass-123")
        unassigned_lead = AdmissionLead.objects.create(
            learner_name="Unassigned Lead",
            phone="0710000003",
            campus=None,
        )

        list_response = self.client.get(reverse("admin_admissions_leads"))
        hidden_edit_response = self.client.get(reverse("admin_admissions_lead_edit", kwargs={"pk": self.hidden_lead.pk}))
        convert_response = self.client.get(reverse("admin_admissions_lead_convert", kwargs={"pk": unassigned_lead.pk}))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Visible Lead")
        self.assertContains(list_response, "Unassigned Lead")
        self.assertNotContains(list_response, "Hidden Lead")
        self.assertEqual(hidden_edit_response.status_code, 404)
        self.assertEqual(convert_response.status_code, 302)
        unassigned_lead.refresh_from_db()
        self.assertEqual(unassigned_lead.campus, self.campus)
        self.assertTrue(Applicant.objects.filter(first_name="Unassigned", last_name="Lead", campus=self.campus).exists())

    def test_campus_admin_templates_are_scoped_for_list_and_edit(self):
        self.client.login(username="admissions_campus_admin", password="test-pass-123")

        list_response = self.client.get(reverse("admin_admissions_form_templates"))
        hidden_edit_response = self.client.get(reverse("admin_admissions_form_template_edit", kwargs={"pk": self.hidden_template.pk}))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Visible Template")
        self.assertNotContains(list_response, "Hidden Template")
        self.assertEqual(hidden_edit_response.status_code, 404)
