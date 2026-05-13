from django.contrib.auth.hashers import make_password
from django.test import SimpleTestCase

from apps.tenant.parents.forms import ParentResultsPinSelfServiceForm
from apps.tenant.parents.models import ParentProfile


class ParentResultsPinSelfServiceFormTests(SimpleTestCase):
    def test_set_pin_when_none_exists(self):
        parent = ParentProfile(first_name="A", last_name="B", results_access_pin_hash="")
        form = ParentResultsPinSelfServiceForm(
            data={"new_pin": "4242", "confirm_pin": "4242", "clear_pin": False},
            parent_profile=parent,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_clear_requires_current_pin(self):
        parent = ParentProfile(
            first_name="A",
            last_name="B",
            results_access_pin_hash=make_password("9999"),
        )
        form = ParentResultsPinSelfServiceForm(
            data={
                "current_pin": "0000",
                "new_pin": "",
                "confirm_pin": "",
                "clear_pin": True,
            },
            parent_profile=parent,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("current_pin", form.errors)

    def test_change_requires_current_pin(self):
        parent = ParentProfile(
            first_name="A",
            last_name="B",
            results_access_pin_hash=make_password("1111"),
        )
        form = ParentResultsPinSelfServiceForm(
            data={
                "current_pin": "",
                "new_pin": "2222",
                "confirm_pin": "2222",
                "clear_pin": False,
            },
            parent_profile=parent,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("current_pin", form.errors)

    def test_clear_and_new_mutually_exclusive(self):
        parent = ParentProfile(
            first_name="A",
            last_name="B",
            results_access_pin_hash=make_password("1111"),
        )
        form = ParentResultsPinSelfServiceForm(
            data={
                "current_pin": "1111",
                "new_pin": "2222",
                "confirm_pin": "2222",
                "clear_pin": True,
            },
            parent_profile=parent,
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())
