from __future__ import annotations

from django.apps import apps
from django.core.exceptions import FieldError
from django.urls import NoReverseMatch, reverse

from apps.tenant.users.models import Role


PHASES = (
    {
        "number": 1,
        "title": "Institution, curriculum and terminology",
        "summary": "Education profiles, curriculum frameworks, education stages and locally configurable terminology.",
        "icon": "ph-buildings",
        "tone": "blue",
        "metric_model": "education_frameworks.InstitutionEducationProfile",
    },
    {
        "number": 2,
        "title": "Assessment framework",
        "summary": "Configurable assessment types, weighting schemes and compatibility links to existing marks and exam papers.",
        "icon": "ph-check-square-offset",
        "tone": "indigo",
        "metric_model": "assessments.AssessmentType",
    },
    {
        "number": 3,
        "title": "Learning activities",
        "summary": "Unified materials, assignments, projects, practical work, discussions, completion and submission policies.",
        "icon": "ph-notebook",
        "tone": "violet",
        "metric_model": "coursework.LearningActivity",
    },
    {
        "number": 4,
        "title": "Grading and report rules",
        "summary": "Level-specific grading profiles, report-card rules and consistent result interpretation.",
        "icon": "ph-chart-line-up",
        "tone": "emerald",
        "metric_model": "assessments.GradingProfile",
    },
    {
        "number": 5,
        "title": "Programme pathways",
        "summary": "Programme pathways, level progression, subject combinations and class-group offering planning.",
        "icon": "ph-path",
        "tone": "cyan",
        "metric_model": "academics.ProgrammePathway",
    },
    {
        "number": 6,
        "title": "External examinations",
        "summary": "Examination boards, centres, sessions, candidate registration, exports and official result imports.",
        "icon": "ph-certificate",
        "tone": "amber",
        "metric_model": "exams.ExternalExamSession",
    },
    {
        "number": 7,
        "title": "Boarding and welfare",
        "summary": "Boarding profiles, leave workflows, guardian handover, hostel roll calls and welfare case follow-up.",
        "icon": "ph-house-line",
        "tone": "rose",
        "metric_model": "hostels.BoardingProfile",
    },
    {
        "number": 8,
        "title": "Clubs, sports and co-curricular life",
        "summary": "Programme profiles, participation safeguards, groups, sessions, attendance and learner achievements.",
        "icon": "ph-trophy",
        "tone": "orange",
        "metric_model": "activities.ActivityProgramme",
    },
    {
        "number": 9,
        "title": "Fees and assessment clearance",
        "summary": "Advisory or blocking clearance rules around live invoices and payments, with approved exceptions.",
        "icon": "ph-shield-check",
        "tone": "green",
        "metric_model": "finance.ClearancePolicy",
    },
)


ROLE_LABELS = {
    "admin": "Full administrator",
    "campus_admin": "Campus administrator",
    "teacher": "Teacher",
    "student": "Student",
    "parent": "Parent or guardian",
}


def portal_role(user) -> str:
    if getattr(user, "is_superuser", False) or user.has_role(Role.ADMIN):
        return "admin"
    if user.has_role(Role.CAMPUS_ADMIN):
        return "campus_admin"
    if user.has_role(Role.TEACHER):
        return "teacher"
    if user.has_role(Role.STUDENT):
        return "student"
    if user.has_role(Role.PARENT):
        return "parent"
    return "student"


def _safe_reverse(route_name: str) -> str:
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return ""


def _safe_count(model_label: str, filters: dict | None = None) -> int:
    try:
        model = apps.get_model(model_label)
        queryset = model.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return queryset.count()
    except (LookupError, FieldError, AttributeError):
        return 0


def _action(label: str, route_name: str, *, description: str = "", primary: bool = False):
    url = _safe_reverse(route_name)
    if not url:
        return None
    return {
        "label": label,
        "url": url,
        "description": description,
        "primary": primary,
    }


def _actions(*items):
    return [item for item in items if item]


def _role_actions(role: str):
    if role == "admin":
        return {
            1: _actions(
                _action("Education framework", "admin_education_framework_dashboard", primary=True),
                _action("Academic setup", "admin_academics_setup"),
            ),
            2: _actions(
                _action("Assessment framework", "admin_assessment_framework_dashboard", primary=True),
                _action("Assessment records", "admin_assessments_list"),
            ),
            3: _actions(
                _action("Learning activity framework", "admin_coursework_activity_framework", primary=True),
                _action("Coursework dashboard", "admin_coursework_dashboard"),
            ),
            4: _actions(
                _action("Grading framework", "admin_grading_framework_dashboard", primary=True),
                _action("Report cards", "admin_term_report_cards"),
            ),
            5: _actions(
                _action("Pathways and combinations", "admin_pathway_dashboard", primary=True),
                _action("Offering planner", "admin_pathway_offerings"),
            ),
            6: _actions(
                _action("External examinations", "admin_external_exam_dashboard", primary=True),
                _action("Internal examinations", "admin_exams_list"),
            ),
            7: _actions(
                _action("Boarding and welfare", "admin_boarding_welfare_dashboard", primary=True),
                _action("Operational readiness", "admin_boarding_welfare_hardening"),
            ),
            8: _actions(
                _action("Co-curricular programmes", "admin_activity_programme_dashboard", primary=True),
                _action("Sessions and attendance", "admin_activity_sessions"),
            ),
            9: _actions(
                _action("Clearance policies", "admin_finance_clearance_dashboard", primary=True),
                _action("Check a learner", "admin_finance_clearance_learner_check"),
            ),
        }
    if role == "campus_admin":
        return {
            1: [],
            2: _actions(_action("Assessment operations", "admin_assessments_list", primary=True)),
            3: _actions(_action("Coursework operations", "admin_coursework_dashboard", primary=True)),
            4: _actions(_action("Mark tabulation", "admin_assessments_tabulation", primary=True)),
            5: _actions(
                _action("Classes and offerings", "admin_offering_list", primary=True),
                _action("Class streams", "admin_stream_list"),
            ),
            6: _actions(_action("Internal examination operations", "admin_exams_list", primary=True)),
            7: _actions(
                _action("Boarding and welfare", "admin_boarding_welfare_dashboard", primary=True),
                _action("Operational readiness", "admin_boarding_welfare_hardening"),
            ),
            8: _actions(
                _action("Sessions and attendance", "admin_activity_sessions", primary=True),
                _action("Activities and clubs", "admin_activities_list"),
            ),
            9: _actions(
                _action("Finance dashboard", "admin_finance_dashboard", primary=True),
                _action("Invoices", "admin_invoices_list"),
            ),
        }
    if role == "teacher":
        return {
            1: [],
            2: _actions(_action("My assessments", "teacher_assessments_home", primary=True)),
            3: _actions(_action("My coursework", "teacher_coursework_home", primary=True)),
            4: _actions(_action("Assessment marking", "teacher_assessments_home", primary=True)),
            5: _actions(
                _action("My timetable", "teacher_timetable", primary=True),
                _action("My coursework", "teacher_coursework_home"),
            ),
            6: _actions(_action("Final examinations", "teacher_exams_home", primary=True)),
            7: _actions(
                _action("Learner incidents", "teacher_incidents_list", primary=True),
                _action("Raise a concern", "teacher_grievances_submit"),
            ),
            8: [],
            9: _actions(_action("Examination workspace", "teacher_exams_home", primary=True)),
        }
    if role == "student":
        return {
            1: [],
            2: _actions(_action("My assessment results", "student_results_home", primary=True)),
            3: _actions(_action("My coursework", "student_coursework_home", primary=True)),
            4: _actions(
                _action("My report card", "student_report_card", primary=True),
                _action("Assessment results", "student_results_home"),
            ),
            5: _actions(
                _action("My timetable", "student_timetable", primary=True),
                _action("My coursework", "student_coursework_home"),
            ),
            6: _actions(
                _action("Examination dashboard", "student_exams_dashboard", primary=True),
                _action("Exam results", "student_exam_results"),
                _action("Exam schedules", "student_exam_schedules"),
            ),
            7: _actions(_action("My boarding information", "student_hostel_home", primary=True)),
            8: [],
            9: _actions(
                _action("My invoices and receipts", "student_invoices_list", primary=True),
                _action("Assessment results", "student_results_home"),
            ),
        }
    return {
        1: [],
        2: _actions(_action("Children's assessment results", "parent_results_home", primary=True)),
        3: _actions(_action("Children's coursework", "parent_coursework_home", primary=True)),
        4: _actions(_action("Children's report cards", "parent_results_home", primary=True)),
        5: _actions(_action("Learning progress", "parent_coursework_home", primary=True)),
        6: _actions(_action("External and internal exam results", "parent_exam_results", primary=True)),
        7: _actions(_action("Children's boarding information", "parent_hostel_home", primary=True)),
        8: [],
        9: _actions(
            _action("Invoices, payments and receipts", "parent_invoices_list", primary=True),
            _action("Published results", "parent_results_home"),
        ),
    }


def _managed_message(role: str, phase_number: int) -> str:
    if role == "campus_admin":
        if phase_number in {1, 2, 4, 5, 6, 9}:
            return "Core configuration is controlled by a full administrator; campus-scoped operations remain available where permitted."
    if role == "teacher":
        if phase_number in {1, 8}:
            return "This capability is configured by school administrators and automatically applies to your teaching workspace."
        if phase_number == 9:
            return "Finance officers manage clearance. Existing marks and examination records are never changed by a clearance decision."
    if role in {"student", "parent"}:
        if phase_number in {1, 2, 5}:
            return "The school configures this capability. Its terminology, subject structure and rules are applied automatically in your portal."
        if phase_number == 8:
            return "Participation, session attendance and achievements are recorded by authorised school staff and reflected in learner records."
        if phase_number == 9:
            return "The portal uses live invoices and payments when checking access. Contact the finance office when a clearance message appears."
    return "This capability is managed by authorised school administrators."


def build_capability_context(user, *, role: str | None = None):
    role = role or portal_role(user)
    action_map = _role_actions(role)
    phases = []
    for phase in PHASES:
        row = dict(phase)
        row["actions"] = action_map.get(phase["number"], [])
        row["configured_count"] = _safe_count(phase["metric_model"])
        row["available"] = bool(row["actions"])
        row["status_label"] = "Available in your portal" if row["available"] else "Managed by the school"
        row["managed_message"] = _managed_message(role, phase["number"])
        phases.append(row)

    return {
        "capability_role": role,
        "capability_role_label": ROLE_LABELS.get(role, "Portal user"),
        "capability_phases": phases,
        "capability_available_count": sum(1 for phase in phases if phase["available"]),
        "capability_managed_count": sum(1 for phase in phases if not phase["available"]),
        "capability_action_count": sum(len(phase["actions"]) for phase in phases),
        "capability_is_full_admin": role == "admin",
        "capability_is_campus_admin": role == "campus_admin",
    }
