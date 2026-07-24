from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .dns_targets import (
    A_RECORD_PLACEHOLDER,
    _auto_detect_public_ipv4,
    _clean_public_ipv4,
    get_dns_targets,
)
from .templatetags.platform_dns import platform_dns_target


class PlatformDnsTargetTests(SimpleTestCase):
    def tearDown(self):
        _auto_detect_public_ipv4.cache_clear()
        super().tearDown()

    def test_public_ipv4_validation_rejects_private_and_invalid_values(self):
        self.assertEqual(_clean_public_ipv4("1.1.1.1"), "1.1.1.1")
        self.assertEqual(_clean_public_ipv4("127.0.0.1"), "")
        self.assertEqual(_clean_public_ipv4("192.168.1.10"), "")
        self.assertEqual(_clean_public_ipv4("not-an-ip"), "")

    @override_settings(
        EDUMANAGE_PUBLIC_IPV4="1.1.1.1",
        EDUMANAGE_CNAME_TARGET="schools.example.com",
        ALLOWED_HOSTS=["platform.example.com"],
    )
    def test_explicit_targets_take_priority(self):
        targets = get_dns_targets()

        self.assertEqual(targets["a_record_target"], "1.1.1.1")
        self.assertTrue(targets["a_record_ready"])
        self.assertEqual(targets["a_record_source"], "Configured by EDUMANAGE_PUBLIC_IPV4")
        self.assertEqual(targets["cname_target"], "schools.example.com")
        self.assertEqual(platform_dns_target("A"), "1.1.1.1")
        self.assertEqual(platform_dns_target("CNAME"), "schools.example.com")

    @override_settings(
        EDUMANAGE_PUBLIC_IPV4="",
        EDUMANAGE_CNAME_TARGET="",
        EDUMANAGE_ORIGIN_HOST="platform.example.com",
        ENVIRONMENT="production",
        ALLOWED_HOSTS=["platform.example.com"],
    )
    @patch("apps.public.tenants.dns_targets._resolve_origin_ipv4", return_value="")
    @patch("apps.public.tenants.dns_targets._fetch_public_ipv4", return_value="8.8.8.8")
    def test_production_automatically_detects_public_ipv4(self, fetch_public_ip, resolve_origin):
        _auto_detect_public_ipv4.cache_clear()

        targets = get_dns_targets()

        self.assertEqual(targets["a_record_target"], "8.8.8.8")
        self.assertTrue(targets["a_record_ready"])
        self.assertIn("Auto-detected", targets["a_record_source"])
        self.assertEqual(targets["cname_target"], "platform.example.com")
        fetch_public_ip.assert_called_once_with()
        resolve_origin.assert_not_called()

    @override_settings(
        EDUMANAGE_PUBLIC_IPV4="127.0.0.1",
        EDUMANAGE_CNAME_TARGET="",
        EDUMANAGE_ORIGIN_HOST="",
        ENVIRONMENT="test",
        ALLOWED_HOSTS=["testserver"],
    )
    @patch("apps.public.tenants.dns_targets._resolve_origin_ipv4", return_value="")
    @patch("apps.public.tenants.dns_targets._fetch_public_ipv4")
    def test_unavailable_detection_keeps_safe_placeholder(self, fetch_public_ip, resolve_origin):
        _auto_detect_public_ipv4.cache_clear()

        targets = get_dns_targets()

        self.assertEqual(targets["a_record_target"], A_RECORD_PLACEHOLDER)
        self.assertFalse(targets["a_record_ready"])
        fetch_public_ip.assert_not_called()
        resolve_origin.assert_called_once_with()
