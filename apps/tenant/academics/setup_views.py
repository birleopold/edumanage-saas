from django.shortcuts import render
from django.urls import reverse

from apps.tenant.education_frameworks.models import CampusEducationStage
from apps.tenant.portals.permissions import admin_portal_required

from .models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Level, Program


@admin_portal_required
def academics_setup(request):
    items = [
        {
            "label": "Education Framework",
            "description": "Set institution levels, curriculum defaults and familiar local terminology without changing existing records.",
            "count": CampusEducationStage.objects.filter(is_active=True).count(),
            "list_url": reverse("admin_education_framework_dashboard"),
            "add_url": reverse("admin_education_framework_dashboard"),
            "add_label": "Configure",
            "icon": "ph-globe-hemisphere-west",
        },
        {
            "label": "Academic Years",
            "description": "Create school years and mark the current academic year.",
            "count": AcademicYear.objects.count(),
            "list_url": reverse("admin_academic_year_list"),
            "add_url": reverse("admin_academic_year_create"),
            "icon": "ph-calendar",
        },
        {
            "label": "Academic Terms",
            "description": "Set terms under each academic year and choose the current term.",
            "count": AcademicTerm.objects.count(),
            "list_url": reverse("admin_academic_term_list"),
            "add_url": reverse("admin_academic_term_create"),
            "icon": "ph-calendar-check",
        },
        {
            "label": "Levels",
            "description": "Define school levels such as Nursery, Primary, O-Level or A-Level.",
            "count": Level.objects.count(),
            "list_url": reverse("admin_level_list"),
            "add_url": reverse("admin_level_create"),
            "icon": "ph-stairs",
        },
        {
            "label": "Programs",
            "description": "Group academic programs or sections offered by the school.",
            "count": Program.objects.count(),
            "list_url": reverse("admin_program_list"),
            "add_url": reverse("admin_program_create"),
            "icon": "ph-tree-structure",
        },
        {
            "label": "Class Groups",
            "description": "Create class groups such as P1, S1, Year 7 or Grade 5.",
            "count": ClassGroup.objects.count(),
            "list_url": reverse("admin_classgroup_list"),
            "add_url": reverse("admin_classgroup_create"),
            "icon": "ph-users-three",
        },
        {
            "label": "Courses",
            "description": "Create subjects or courses taught by the school.",
            "count": Course.objects.count(),
            "list_url": reverse("admin_course_list"),
            "add_url": reverse("admin_course_create"),
            "icon": "ph-books",
        },
        {
            "label": "Course Offerings",
            "description": "Connect courses to terms, classes, campuses and teachers.",
            "count": CourseOffering.objects.count(),
            "list_url": reverse("admin_offering_list"),
            "add_url": reverse("admin_offering_create"),
            "icon": "ph-chalkboard-teacher",
        },
        {
            "label": "Enrollments",
            "description": "Enroll students into course offerings and manage class-course membership.",
            "count": Enrollment.objects.count(),
            "list_url": reverse("admin_enrollment_list"),
            "add_url": reverse("admin_enrollment_create"),
            "icon": "ph-user-plus",
        },
    ]
    return render(request, "portals/admin/academics/setup.html", {"items": items})
