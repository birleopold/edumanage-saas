from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .models import DocumentTemplate
from .schema import validate_design_document
from .services import default_design, page_dimensions_for


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
