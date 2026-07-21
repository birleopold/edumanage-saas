import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def visible_template_text(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


class PortalEditorialQualityTests(SimpleTestCase):
    def test_live_portal_templates_do_not_expose_development_labels(self):
        portal_templates = Path(settings.BASE_DIR) / "templates" / "portals"
        forbidden = {
            "numbered development phase": re.compile(r"\bphase\s+[1-9]\b", re.IGNORECASE),
            "modernisation wording": re.compile(r"\bmoderni[sz]ation\b", re.IGNORECASE),
            "rollout wording": re.compile(r"\brollout hardening\b", re.IGNORECASE),
            "orchestration wording": re.compile(r"\borchestration\b", re.IGNORECASE),
            "consolidation wording": re.compile(r"\bconsolidation\b", re.IGNORECASE),
            "operational hardening wording": re.compile(r"\boperational hardening\b", re.IGNORECASE),
            "compatibility-first wording": re.compile(r"\bcompatibility-first\b", re.IGNORECASE),
        }

        failures = []
        for template in sorted(portal_templates.rglob("*.html")):
            text = template.read_text(encoding="utf-8")
            visible_text = visible_template_text(text)
            for label, pattern in forbidden.items():
                match = pattern.search(visible_text)
                if match:
                    line = visible_text.count("\n", 0, match.start()) + 1
                    failures.append(
                        f"{template.relative_to(settings.BASE_DIR)}:{line}: {label}: {match.group(0)!r}"
                    )

        self.assertEqual(
            failures,
            [],
            "Development wording must stay out of live portal pages:\n" + "\n".join(failures),
        )

    def test_html_comments_are_not_treated_as_visible_page_copy(self):
        text = "<!-- Phase 7 consolidation --><p>Boarding &amp; Welfare</p>"

        visible_text = visible_template_text(text)

        self.assertNotIn("Phase 7", visible_text)
        self.assertNotIn("consolidation", visible_text)
        self.assertIn("Boarding &amp; Welfare", visible_text)

    def test_navigation_script_uses_human_tool_labels(self):
        script = (
            Path(settings.BASE_DIR) / "static" / "js" / "phase-capability-nav.js"
        ).read_text(encoding="utf-8")

        self.assertIn("All tools", script)
        self.assertIn("More shortcuts", script)
        self.assertNotIn("Phase 1–9 Features", script)
        self.assertNotRegex(script, re.compile(r"\bphase\s+[1-9]\b", re.IGNORECASE))
