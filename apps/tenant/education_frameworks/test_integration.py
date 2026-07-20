from django.template import Context, Template
from django.test import RequestFactory, TestCase

from apps.tenant.orgsettings.models import Campus, OrganizationProfile

from .integration import (
    assessment_aliases_for_request,
    external_exam_aliases_for_request,
    framework_aliases_for_request,
    terminology_for_request,
)
from .models import CampusEducationStage, EducationStage, FrameworkStage
from .services import ensure_institution_profile, ensure_system_templates


class EducationFrameworkIntegrationTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(
            name="Integration Test School"
        )
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.stages, self.frameworks = ensure_system_templates()
        self.profile = ensure_institution_profile(self.organization)
        self.request = RequestFactory().get("/")
        self.request.session = {}

    def test_request_helpers_return_uganda_aliases_when_enabled(self):
        terms = terminology_for_request(self.request)
        aliases = assessment_aliases_for_request(self.request)
        all_aliases = framework_aliases_for_request(self.request)

        self.assertEqual(
            terms["external_exam"],
            "UNEB or External Exam",
        )
        self.assertEqual(
            aliases["BOT"],
            "Beginning of Term Test",
        )
        self.assertEqual(
            aliases["EOT"],
            "End of Term Examination",
        )
        self.assertEqual(
            all_aliases["MDD"],
            "Music, Dance and Drama",
        )

    def test_template_tag_can_be_adopted_without_changing_existing_models(self):
        primary = self.stages[EducationStage.PRIMARY]
        CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=primary,
            framework_stage=FrameworkStage.objects.get(
                framework=self.frameworks["UG-NATIONAL"],
                stage=primary,
            ),
            local_name="Primary",
            academic_period_type=EducationStage.PERIOD_TERM,
        )
        self.profile.terminology = {"learner": "Pupil"}
        self.profile.save(
            update_fields=["terminology", "updated_at"]
        )
        template = Template(
            "{% load education_terms %}"
            "{% education_term 'learner' %} | "
            "{% education_alias 'MOT' %} | "
            "{% education_alias 'MDD' %}"
        )

        rendered = template.render(
            Context({"request": self.request})
        )

        self.assertEqual(
            rendered,
            "Pupil | Mid-Term Test | Music, Dance and Drama",
        )

    def test_external_exam_aliases_are_deduplicated(self):
        self.profile.settings = {
            "external_exam_aliases": [
                "UCE",
                "Cambridge",
                "Cambridge",
            ]
        }
        self.profile.save(update_fields=["settings", "updated_at"])

        aliases = external_exam_aliases_for_request(self.request)

        self.assertEqual(
            aliases,
            ["PLE", "UCE", "UACE", "UNEB", "Cambridge"],
        )

    def test_local_aliases_are_disabled_in_neutral_mode(self):
        self.profile.use_local_terminology = False
        self.profile.save(
            update_fields=["use_local_terminology", "updated_at"]
        )

        aliases = framework_aliases_for_request(self.request)
        template = Template(
            "{% load education_terms %}"
            "{% education_alias 'BOT' 'Diagnostic Assessment' %}"
        )

        self.assertEqual(aliases, {})
        self.assertEqual(
            template.render(Context({"request": self.request})),
            "Diagnostic Assessment",
        )
