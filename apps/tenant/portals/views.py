from django.shortcuts import render, redirect
from django.urls import reverse

from apps.tenant.orgsettings.services import (
    campus_queryset,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)

from apps.tenant.academics.models import AcademicTerm, AcademicYear, CourseOffering, Enrollment
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .permissions import role_required


def landing_page(request):
    """
    Landing page with smart redirect based on user authentication and role.
    - If authenticated: redirect to appropriate portal based on user's role
    - If not authenticated: show portal selection page with login prompt
    """
    if request.user.is_authenticated:
        # Get user's role and redirect to appropriate portal
        user_role = getattr(request.user, 'role', None)
        
        if user_role == Role.ADMIN:
            return redirect('admin_home')
        elif user_role == Role.TEACHER:
            return redirect('teacher_home')
        elif user_role == Role.STUDENT:
            return redirect('student_home')
        elif user_role == Role.PARENT:
            return redirect('parent_home')
        else:
            # If no role or unknown role, redirect to login
            return redirect('login')
    
    # Not authenticated - show beautiful landing page
    return render(request, 'landing.html')


@role_required(Role.ADMIN)
def admin_home(request):
    students_total = StudentProfile.objects.count()
    students_active = StudentProfile.objects.filter(is_active=True).count()
    teachers_total = TeacherProfile.objects.count()
    teachers_active = TeacherProfile.objects.filter(is_active=True).count()
    parents_total = ParentProfile.objects.count()
    parents_active = ParentProfile.objects.filter(is_active=True).count()

    current_year = AcademicYear.objects.filter(is_current=True).order_by("-name").first()
    current_term = AcademicTerm.objects.filter(is_current=True).select_related("year").first()

    offerings_total = CourseOffering.objects.count()
    offerings_active = CourseOffering.objects.filter(is_active=True).count()
    enrollments_total = Enrollment.objects.count()
    enrollments_active = Enrollment.objects.filter(status=Enrollment.ACTIVE).count()

    return render(
        request,
        "portals/admin/home.html",
        {
            "students_total": students_total,
            "students_active": students_active,
            "teachers_total": teachers_total,
            "teachers_active": teachers_active,
            "parents_total": parents_total,
            "parents_active": parents_active,
            "current_year": current_year,
            "current_term": current_term,
            "offerings_total": offerings_total,
            "offerings_active": offerings_active,
            "enrollments_total": enrollments_total,
            "enrollments_active": enrollments_active,
        },
    )


@role_required(Role.TEACHER)
def teacher_home(request):
    return render(request, "portals/teacher/home.html")


@role_required(Role.STUDENT)
def student_home(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    return render(request, "portals/student/home.html", {"student": student})


@role_required(Role.PARENT)
def parent_home(request):
    update_current_campus_from_request(request)

    parent_profile = ParentProfile.objects.filter(user=request.user).first()
    links = []
    if parent_profile:
        qs = (
            ParentStudentLink.objects.filter(parent=parent_profile)
            .select_related("student", "student__campus")
            .order_by("-is_primary", "student__last_name", "student__first_name")
        )

        campus_id = selected_campus_id_from_request(request)
        if campus_id:
            qs = qs.filter(student__campus_id=campus_id)

        links = list(qs)

    campuses = campus_queryset()
    selected_campus_id = selected_campus_id_from_request(request)

    groups = {}
    for link in links:
        key = link.student.campus.name if getattr(link.student, "campus", None) else "Unassigned"
        groups.setdefault(key, []).append(link)

    return render(
        request,
        "portals/parent/home.html",
        {
            "parent_profile": parent_profile,
            "links": links,
            "children_groups": list(groups.items()),
            "campuses": campuses,
            "selected_campus_id": selected_campus_id,
        },
    )
