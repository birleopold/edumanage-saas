from django.test import SimpleTestCase

from apps.tenant.education_frameworks.models import EducationStage, InstitutionEducationProfile

from .setup_center import _step, _uganda_reference_for_type


class SchoolSetupCenterGuidanceTests(SimpleTestCase):
    def test_primary_uganda_reference_only_shows_primary_structure(self):
        rows = _uganda_reference_for_type(InstitutionEducationProfile.PRIMARY)

        self.assertEqual([row["code"] for row in rows], [EducationStage.PRIMARY])
        self.assertEqual(rows[0]["levels"], ("P1", "P2", "P3", "P4", "P5", "P6", "P7"))
        self.assertEqual(rows[0]["exit_exam"], "PLE")

    def test_secondary_uganda_reference_separates_o_and_a_level(self):
        rows = _uganda_reference_for_type(InstitutionEducationProfile.SECONDARY)

        self.assertEqual(
            [row["code"] for row in rows],
            [EducationStage.LOWER_SECONDARY, EducationStage.UPPER_SECONDARY],
        )
        self.assertEqual(rows[0]["levels"], ("S1", "S2", "S3", "S4"))
        self.assertEqual(rows[0]["exit_exam"], "UCE")
        self.assertEqual(rows[1]["levels"], ("S5", "S6"))
        self.assertEqual(rows[1]["exit_exam"], "UACE")

    def test_higher_education_does_not_receive_school_level_reference(self):
        self.assertEqual(
            _uganda_reference_for_type(InstitutionEducationProfile.UNIVERSITY),
            [],
        )

    def test_optional_setup_does_not_look_like_blocking_failure(self):
        row = _step(
            key="attendance",
            number=9,
            title="Attendance",
            description="Optional operations",
            done=False,
            evidence=[],
            primary_label="Attendance",
            primary_url_name="admin_attendance_device_dashboard",
            optional=True,
        )

        self.assertEqual(row["status"], "optional")
        self.assertTrue(row["optional"])
        self.assertFalse(row["done"])
