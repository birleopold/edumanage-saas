from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.tenant.students.models import StudentProfile

from .forms import DocumentGenerationForm
from .models import DocumentTemplate, DocumentTemplateVersion, IssuedDocument
from .schema import validate_design_document
from .services import (
    activate_version,
    approve_version,
    default_design,
    get_editable_version,
    page_dimensions_for,
    render_version_pdf,
    submit_for_review,
)


class DesignSchemaTests(SimpleTestCase):
    def test_default_designs_validate(self):
        for document_type, _label in DocumentTemplate.DOCUMENT_TYPE_CHOICES:
            width, height = page_dimensions_for(document_type)
            validate_design_document(default_design(document_type), width, height)

    def test_unknown_binding_is_rejected(self):
        design = {"pages": [{"id": "p1", "elements": [{"id": "x", "type": "field", "binding": "student.password", "x": 1, "y": 1, "width": 10, "height": 5}]}]}
        with self.assertRaises(ValidationError):
            validate_design_document(design, 85.6, 54)

    def test_out_of_bounds_element_is_rejected(self):
        design = {"pages": [{"id": "p1", "elements": [{"id": "x", "type": "text", "text": "Hello", "x": 80, "y": 1, "width": 10, "height": 5}]}]}
        with self.assertRaises(ValidationError):
            validate_design_document(design, 85.6, 54)

    def test_generation_form_has_no_student_photo_schema_dependency(self):
        self.assertNotIn("student_photo", DocumentGenerationForm().fields)


class DesignVersionLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="design-approver", password="test-pass-123")
        self.template = DocumentTemplate.objects.create(name="Official report", document_type=DocumentTemplate.REPORT_CARD)
        width, height = page_dimensions_for(DocumentTemplate.REPORT_CARD)
        self.version = DocumentTemplateVersion.objects.create(
            template=self.template,
            number=1,
            design=default_design(DocumentTemplate.REPORT_CARD),
            page_width_mm=width,
            page_height_mm=height,
            created_by=self.user,
        )

    def test_official_version_is_immutable_and_revision_is_explicit(self):
        submit_for_review(self.version, self.user)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, DocumentTemplateVersion.IN_REVIEW)
        self.assertTrue(self.version.is_locked)

        submitted_change = dict(self.version.design)
        submitted_change["version"] = 99
        self.version.design = submitted_change
        with self.assertRaises(ValidationError):
            self.version.save()
        self.version.refresh_from_db()

        approve_version(self.version, self.user)
        activate_version(self.version, self.user)
        self.version.refresh_from_db()
        self.template.refresh_from_db()
        self.assertEqual(self.version.status, DocumentTemplateVersion.ACTIVE)
        self.assertEqual(self.template.active_version_number, 1)

        changed = dict(self.version.design)
        changed["version"] = 2
        self.version.design = changed
        with self.assertRaises(ValidationError):
            self.version.save()

        self.version.refresh_from_db()
        draft = get_editable_version(self.template, self.user)
        self.assertEqual(draft.status, DocumentTemplateVersion.DRAFT)
        self.assertEqual(draft.number, 2)
        self.assertEqual(draft.design, self.version.design)

    def test_student_id_pdf_renders_without_student_photo_field(self):
        student = StudentProfile.objects.create(
            student_id="STD-001",
            first_name="Amina",
            last_name="Nabirye",
        )
        template = DocumentTemplate.objects.create(name="Student identity", document_type=DocumentTemplate.STUDENT_ID)
        width, height = page_dimensions_for(DocumentTemplate.STUDENT_ID)
        version = DocumentTemplateVersion.objects.create(
            template=template,
            number=1,
            design=default_design(DocumentTemplate.STUDENT_ID),
            page_width_mm=width,
            page_height_mm=height,
            created_by=self.user,
        )

        pdf = render_version_pdf(version, student, verification_url="https://school.example/verify/demo")

        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))
        self.assertFalse(hasattr(student, "photo"))

    def test_verification_page_distinguishes_active_and_revoked_documents(self):
        student = StudentProfile.objects.create(
            student_id="STD-002",
            first_name="Peter",
            last_name="Kato",
        )
        issued = IssuedDocument.objects.create(
            template=self.template,
            version=self.version,
            student=student,
            reference="REPORT-2026-001",
            data_snapshot={"student": {"full_name": student.get_full_name(), "student_id": student.student_id}},
            issued_by=self.user,
        )
        url = reverse("designstudio:verify", args=[issued.verification_token])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VALID DOCUMENT")
        self.assertContains(response, issued.reference)

        issued.status = IssuedDocument.REVOKED
        issued.revocation_reason = "Reissued with corrected details"
        issued.save(update_fields=["status", "revocation_reason"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "REVOKED / INVALID")
        self.assertContains(response, "Reissued with corrected details")
