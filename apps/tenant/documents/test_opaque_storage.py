from django.db import connection
from django.test import SimpleTestCase

from apps.tenant.admissions.models import applicant_document_upload_to
from apps.tenant.documents.models import document_upload_to


class _Applicant:
    application_reference = "APP-TEST"
    pk = 1


class _ApplicantDocument:
    applicant = _Applicant()
    applicant_id = 1


class OpaqueUploadPathTests(SimpleTestCase):
    def test_school_document_does_not_preserve_original_filename(self):
        path = document_upload_to(object(), "student-medical-letter.pdf")
        self.assertTrue(path.endswith(".pdf"))
        self.assertNotIn("student-medical-letter", path)
        self.assertIn("/documents/", path)

    def test_admission_document_does_not_preserve_original_filename(self):
        path = applicant_document_upload_to(_ApplicantDocument(), "birth-certificate.jpg")
        self.assertTrue(path.endswith(".jpg"))
        self.assertNotIn("birth-certificate", path)
        self.assertIn("/admissions/APP-TEST/", path)
