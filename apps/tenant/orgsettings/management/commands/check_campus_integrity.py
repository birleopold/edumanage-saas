"""
Management command to check campus data integrity across related models.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile


class Command(BaseCommand):
    help = "Check campus data integrity across related models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Automatically fix campus mismatches where possible",
        )

    def handle(self, *args, **options):
        fix_mode = options.get("fix", False)
        issues_found = 0

        self.stdout.write(self.style.WARNING("Checking campus data integrity...\n"))

        # Check Enrollments
        self.stdout.write("Checking Enrollments...")
        enrollments = Enrollment.objects.select_related(
            "student", "offering", "campus"
        ).all()

        for enrollment in enrollments:
            issues = []

            # Check enrollment.campus vs offering.campus
            if enrollment.campus and enrollment.offering.campus:
                if enrollment.campus != enrollment.offering.campus:
                    issues.append(
                        f"Enrollment campus ({enrollment.campus}) != Offering campus ({enrollment.offering.campus})"
                    )

            # Check enrollment.campus vs student.campus
            if enrollment.campus and enrollment.student.campus:
                if enrollment.campus != enrollment.student.campus:
                    issues.append(
                        f"Enrollment campus ({enrollment.campus}) != Student campus ({enrollment.student.campus})"
                    )

            # Check if enrollment has no campus but offering/student do
            if not enrollment.campus:
                if enrollment.offering.campus or enrollment.student.campus:
                    issues.append("Enrollment has no campus but offering/student do")
                    if fix_mode:
                        # Derive campus from offering or student
                        derived_campus = (
                            enrollment.offering.campus or enrollment.student.campus
                        )
                        enrollment.campus = derived_campus
                        enrollment.save(update_fields=["campus"])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Fixed: Set enrollment {enrollment.id} campus to {derived_campus}"
                            )
                        )

            if issues:
                issues_found += len(issues)
                self.stdout.write(
                    self.style.ERROR(f"  Enrollment {enrollment.id}:")
                )
                for issue in issues:
                    self.stdout.write(self.style.ERROR(f"    - {issue}"))

        # Check CourseOfferings
        self.stdout.write("\nChecking CourseOfferings...")
        offerings = CourseOffering.objects.select_related(
            "campus", "class_group", "teacher"
        ).all()

        for offering in offerings:
            issues = []

            # Check offering.campus vs class_group.campus
            if offering.campus and offering.class_group and offering.class_group.campus:
                if offering.campus != offering.class_group.campus:
                    issues.append(
                        f"Offering campus ({offering.campus}) != Class group campus ({offering.class_group.campus})"
                    )

            # Check offering.campus vs teacher.campus
            if offering.campus and offering.teacher and offering.teacher.campus:
                if offering.campus != offering.teacher.campus:
                    issues.append(
                        f"Offering campus ({offering.campus}) != Teacher campus ({offering.teacher.campus})"
                    )

            # Check if offering has no campus but class_group does
            if not offering.campus and offering.class_group and offering.class_group.campus:
                issues.append("Offering has no campus but class group does")
                if fix_mode:
                    offering.campus = offering.class_group.campus
                    offering.save(update_fields=["campus"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Fixed: Set offering {offering.id} campus to {offering.class_group.campus}"
                        )
                    )

            if issues:
                issues_found += len(issues)
                self.stdout.write(
                    self.style.ERROR(f"  Offering {offering.id}:")
                )
                for issue in issues:
                    self.stdout.write(self.style.ERROR(f"    - {issue}"))

        # Summary
        self.stdout.write("\n" + "=" * 50)
        if issues_found == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "✓ No campus integrity issues found!"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {issues_found} campus integrity issue(s)."
                )
            )
            if not fix_mode:
                self.stdout.write(
                    self.style.WARNING(
                        "Run with --fix to automatically fix issues where possible."
                    )
                )
