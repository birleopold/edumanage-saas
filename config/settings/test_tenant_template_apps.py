from django.test import SimpleTestCase

from config.settings import tenants


class TenantTemplateAppRegistrationTests(SimpleTestCase):
    def test_widget_tweaks_is_available_in_tenant_settings(self):
        self.assertIn("widget_tweaks", tenants.SHARED_APPS)
        self.assertIn("widget_tweaks", tenants.INSTALLED_APPS)
