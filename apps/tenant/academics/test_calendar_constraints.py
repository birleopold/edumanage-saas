from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import AcademicTerm, AcademicYear


class CurrentCalendarConstraintTests(TestCase):
    def test_only_one_year_can_be_current_outside_forms(self):
        AcademicYear.objects.create(name="2026", is_current=True)

        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicYear.objects.create(name="2027", is_current=True)

    def test_only_one_term_can_be_current_outside_forms(self):
        first_year = AcademicYear.objects.create(name="2026", is_current=True)
        second_year = AcademicYear.objects.create(name="2027")
        AcademicTerm.objects.create(year=first_year, name="Term 1", is_current=True)

        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicTerm.objects.create(year=second_year, name="Term 1", is_current=True)
