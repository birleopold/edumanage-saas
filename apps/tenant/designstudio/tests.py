from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from .models import DocumentTemplate, DocumentTemplateVersion
from .schema import validate_design_document
from .services import (
    activate_version,
    approve_version,
    default_design,
    get_editable_version,
    page_dimensions_for,
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
