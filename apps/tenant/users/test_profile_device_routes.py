from django.test import SimpleTestCase
from django.urls import reverse


class ProfileDeviceRouteTests(SimpleTestCase):
    def test_my_devices_route_is_available_from_profile(self):
        self.assertEqual(reverse("my_devices"), "/devices/")

    def test_my_device_deactivate_route_is_available(self):
        self.assertEqual(
            reverse("my_device_deactivate", kwargs={"pk": 7}),
            "/devices/7/deactivate/",
        )
