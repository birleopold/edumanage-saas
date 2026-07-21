from django.shortcuts import render
from django.urls import reverse

from apps.tenant.education_frameworks.models import CampusEducationStage
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    Level,
    Program,
    ProgrammePathway,
)


@admin_portal_required
def academics_setup(request):
    items = []
    is_full_admin = bool(
        request.user.is_superuser
        or (hasattr(request.user, "has_role") and request.user.has_role(Role.ADMIN))
    )
    if is_full_admin:
        items.extend(
            [
                {
                    "label": "School Structure",
                    "description": "Set the curriculum, school stages and wording used across the portal.",
                    "count": CampusEducationStage.objects.filter(is_active=True).count(),
                    "list_url": reverse("admin_education_framework_dashboard"),
                    "add_url": reverse("admin_education_framework_dashboard"),
                    "add_label": "Open",
                    "icon": "ph-buildings",
                },
                {
                    "label": "Programme Pathways",
                    "description": "Set programme levels, subject combinations and class assignments.",
                    "count": ProgrammePathway.objects.count(),
                    "list_url": reverse("admin_pathway_dashboard"),
                    "add_url": reverse("admin_pathway_create"),
                    "icon": "ph-path",
                },
            ]
        )

    items.extend(
        [
            {
                "label": "Academic Years",
                "description": "Create school years and mark the current year.",
                "count": AcademicYear.objects.count(),
                "list_url": reverse("admin_academic_year_list"),
                "add_url": reverse("admin_academic_year_create"),
                "icon": "ph-calendar",
            },
            {
                "label": "Terms",
                "description": "Add terms and choose the current term.",
                "count": AcademicTerm.objects.count(),
                "list_url": reverse("admin_academic_term_list"),
                "add_url": reverse("admin_academic_term_create"),
                "icon": "ph-calendar-check",
            },
            {
                "label": "Levels",
                "description": "Add levels such as Nursery, Primary, O-Level or A-Level.",
                "count": Level.objects.count(),
                "list_url": reverse("admin_level_list"),
                "add_url": reverse("admin_level_create"),
                "icon": "ph-stairs",
            },
            {
                "label": "Programmes",
                "description": "Add the programmes or sections offered by the school.",
                "count": Program.objects.count(),
                "list_url": reverse("admin_program_list"),
                "add_url": reverse("admin_program_create"),
                "icon": "ph-tree-structure",
            },
            {
                "label": "Classes",
                "description": "Add classes such as P1, S1, Year 7 or Grade 5.",
                "count": ClassGroup.objects.count(),
                "list_url": reverse("admin_classgroup_list"),
                "add_url": reverse("admin_classgroup_create"),
                "icon": "ph-users-three",
            },
            {
                "label": "Subjects",
                "description": "Add subjects or courses taught by the school.",
                "count": Course.objects.count(),
                "list_url": reverse("admin_course_list"),
                "add_url": reverse("admin_course_create"),
                "icon": "ph-books",
            },
            {
                "label": "Class Subjects",
                "description": "Assign subjects and teachers to classes and terms.",
                "count": CourseOffering.objects.count(),
                "list_url": reverse("admin_offering_list"),
                "add_url": reverse("admin_offering_create"),
                "icon": "ph-chalkboard-teacher",
            },
            {
                "label": "Subject Enrolment",
                "description": "Add learners to the subjects they study.",
                "count": Enrollment.objects.count(),
                "list_url": reverse("admin_enrollment_list"),
                "add_url": reverse("admin_enrollment_create"),
                "icon": "ph-user-plus",
            },
        ]
    )
    return render(
        request,
        "portals/admin/academics/setup.html",
        {"items": items, "can_manage_framework": is_full_admin},
    )
