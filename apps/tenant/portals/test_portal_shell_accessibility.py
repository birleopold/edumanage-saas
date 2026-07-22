from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class PortalShellAccessibilityTests(SimpleTestCase):
    def test_shared_portal_component_loads_shell_controller(self):
        component = (
            Path(settings.BASE_DIR) / "templates" / "components" / "ui_portal_polish.html"
        ).read_text(encoding="utf-8")

        self.assertIn("js/portal-shell.js", component)

    def test_all_role_shells_expose_shared_navigation_hooks(self):
        portal_bases = [
            "admin/base.html",
            "teacher/base.html",
            "student/base.html",
            "parent/base.html",
        ]

        for relative_path in portal_bases:
            with self.subTest(portal=relative_path):
                template = (
                    Path(settings.BASE_DIR) / "templates" / "portals" / relative_path
                ).read_text(encoding="utf-8")
                self.assertIn('id="sidebar"', template)
                self.assertIn('id="sidebar-backdrop"', template)
                self.assertIn('aria-controls="sidebar"', template)
                self.assertIn('components/ui_portal_polish.html', template)

    def test_shell_controller_covers_keyboard_focus_and_responsive_state(self):
        script = (
            Path(settings.BASE_DIR) / "static" / "js" / "portal-shell.js"
        ).read_text(encoding="utf-8")

        required_behaviours = [
            'event.key === "Escape"',
            'event.key !== "Tab"',
            'window.matchMedia',
            'aria-expanded',
            'aria-hidden',
            'toggleAttribute("inert"',
            'lastOpener.focus()',
            'window.toggleSidebar',
        ]
        for behaviour in required_behaviours:
            with self.subTest(behaviour=behaviour):
                self.assertIn(behaviour, script)
