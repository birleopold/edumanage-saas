from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from apps.tenant.users.models import Role


ROLE_META = {
    "admin": {
        "label": "Administrator",
        "title": "All tools",
        "intro": "Find every school task in one place.",
    },
    "campus_admin": {
        "label": "Campus administrator",
        "title": "Campus tools",
        "intro": "Open the tools available for your campus.",
    },
    "teacher": {
        "label": "Teacher",
        "title": "Teaching tools",
        "intro": "Everything you need for lessons, marking and learner support.",
    },
    "student": {
        "label": "Student",
        "title": "My school",
        "intro": "Coursework, results, school services and account information.",
    },
    "parent": {
        "label": "Parent or guardian",
        "title": "My children",
        "intro": "Learning, wellbeing, fees and school services in one place.",
    },
}


def _action(label: str, route: str, *, primary: bool = False):
    return {"label": label, "route": route, "primary": primary}


def _tool(key: str, title: str, summary: str, icon: str, *actions):
    return {
        "key": key,
        "title": title,
        "summary": summary,
        "icon": icon,
        "actions": actions,
    }


ROLE_TOOL_GROUPS = {
    "admin": (
        {
            "name": "People",
            "tools": (
                _tool("students", "Students", "Profiles, admissions and bulk imports.", "ph-student", _action("View students", "admin_students_list", primary=True), _action("Add student", "admin_students_create")),
                _tool("admissions", "Admissions", "Applications and enrolment decisions.", "ph-clipboard-text", _action("Open admissions", "admin_admissions_applicants", primary=True)),
                _tool("teachers", "Teachers", "Teacher profiles and staff records.", "ph-chalkboard-teacher", _action("View teachers", "admin_teachers_list", primary=True), _action("Add teacher", "admin_teachers_create")),
                _tool("parents", "Parents", "Parent profiles, links and communication.", "ph-users", _action("View parents", "admin_parents_list", primary=True), _action("Add parent", "admin_parents_create")),
                _tool("users", "User accounts", "Roles, access and account management.", "ph-user-gear", _action("Manage users", "admin_users_list", primary=True)),
            ),
        },
        {
            "name": "Teaching & learning",
            "tools": (
                _tool("school-setup", "School setup", "Terms, levels, programmes and school wording.", "ph-buildings", _action("Academic setup", "admin_academics_setup", primary=True), _action("Education settings", "admin_education_framework_dashboard")),
                _tool("classes", "Classes & subjects", "Classes, streams, subjects, offerings and enrolments.", "ph-books", _action("Classes & offerings", "admin_offering_list", primary=True), _action("Enrolments", "admin_enrollment_list")),
                _tool("coursework", "Coursework", "Materials, assignments, submissions and learning activities.", "ph-notebook", _action("Open coursework", "admin_coursework_dashboard", primary=True), _action("Activity settings", "admin_coursework_activity_framework")),
                _tool("attendance", "Attendance & timetable", "Class attendance, lesson schedules and teacher duty.", "ph-calendar-check", _action("Attendance", "admin_attendance_sessions_list", primary=True), _action("Timetable", "admin_timetable_entries_list")),
                _tool("assessments", "Assessments & marks", "Assessments, weighting, marks and tabulation.", "ph-exam", _action("Assessments", "admin_assessments_list", primary=True), _action("Mark sheets", "admin_assessments_tabulation")),
                _tool("grading", "Results & report cards", "Grading rules, report cards and result presentation.", "ph-chart-line-up", _action("Grading settings", "admin_grading_framework_dashboard", primary=True), _action("Report cards", "admin_term_report_cards")),
                _tool("exams", "Exams", "Exam papers, schedules, candidates and results.", "ph-file-text", _action("Internal exams", "admin_exams_list", primary=True), _action("External exams", "admin_external_exam_dashboard")),
                _tool("activities", "Clubs & activities", "Clubs, sports, sessions, attendance and achievements.", "ph-trophy", _action("Activities", "admin_activities_list", primary=True), _action("Sessions", "admin_activity_sessions")),
            ),
        },
        {
            "name": "Student services",
            "tools": (
                _tool("boarding", "Boarding & welfare", "Hostels, rooms, leave, roll calls and learner support.", "ph-house-line", _action("Boarding & welfare", "admin_boarding_welfare_dashboard", primary=True), _action("Hostels", "admin_hostels_list")),
                _tool("health", "Health", "Sickbay visits, treatment and follow-up.", "ph-first-aid-kit", _action("Open sickbay", "admin_sickbay_dashboard", primary=True)),
                _tool("discipline", "Discipline", "Incidents, actions and learner conduct records.", "ph-gavel", _action("Discipline records", "admin_incidents_list", primary=True)),
                _tool("concerns", "Concerns", "Questions, complaints and follow-up.", "ph-chats-circle", _action("View concerns", "admin_grievances_list", primary=True)),
                _tool("library", "Library", "Books, copies, loans, returns and fines.", "ph-book-bookmark", _action("Open library", "admin_library_books_list", primary=True)),
                _tool("transport", "Transport", "Vehicles, routes, stops and student assignments.", "ph-bus", _action("Transport routes", "admin_transport_routes_list", primary=True)),
                _tool("documents", "Documents", "School files shared with staff, learners and parents.", "ph-files", _action("Open documents", "admin_documents_list", primary=True)),
            ),
        },
        {
            "name": "School management",
            "tools": (
                _tool("finance", "Fees & payments", "Invoices, payments, receipts and accounting.", "ph-wallet", _action("Finance dashboard", "admin_finance_dashboard", primary=True), _action("Invoices", "admin_invoices_list")),
                _tool("clearance", "Fees clearance", "Rules and exceptions for exams, results and report cards.", "ph-shield-check", _action("Clearance rules", "admin_finance_clearance_dashboard", primary=True), _action("Check learner", "admin_finance_clearance_learner_check")),
                _tool("announcements", "Announcements", "School notices and communication tools.", "ph-megaphone", _action("Announcements", "admin_announcements_list", primary=True), _action("Communication", "admin_communication_center")),
                _tool("reports", "Reports & analytics", "Academic, attendance, finance and performance reports.", "ph-chart-bar", _action("Reports", "admin_reports_overview", primary=True), _action("Analytics", "admin_analytics_dashboard")),
                _tool("staff", "Staff & payroll", "Staff, departments, payslips and salary settings.", "ph-briefcase", _action("Staff", "admin_hr_staff_list", primary=True), _action("Payslips", "admin_hr_payroll_payslips_list")),
                _tool("inventory", "Inventory", "School items, stock and issue records.", "ph-package", _action("Open inventory", "admin_inventory_items_list", primary=True)),
                _tool("security", "Security & audit", "Activity history, backups and system status.", "ph-lock-key", _action("Audit centre", "audit_dashboard", primary=True), _action("System status", "admin_system_status")),
                _tool("settings", "School settings", "Organisation details, campuses and feature settings.", "ph-gear", _action("School settings", "admin_orgsettings_org", primary=True), _action("Campuses", "admin_orgsettings_campuses")),
            ),
        },
    ),
    "campus_admin": (
        {
            "name": "People",
            "tools": (
                _tool("students", "Students", "Profiles, admissions and bulk imports.", "ph-student", _action("View students", "admin_students_list", primary=True), _action("Add student", "admin_students_create")),
                _tool("admissions", "Admissions", "Applications and enrolment decisions.", "ph-clipboard-text", _action("Open admissions", "admin_admissions_applicants", primary=True)),
                _tool("teachers", "Teachers", "Teacher profiles for your campus.", "ph-chalkboard-teacher", _action("View teachers", "admin_teachers_list", primary=True)),
                _tool("parents", "Parents", "Parent profiles and learner links.", "ph-users", _action("View parents", "admin_parents_list", primary=True)),
            ),
        },
        {
            "name": "Teaching & learning",
            "tools": (
                _tool("classes", "Classes & subjects", "Classes, streams, subjects, offerings and enrolments.", "ph-books", _action("Classes & offerings", "admin_offering_list", primary=True), _action("Enrolments", "admin_enrollment_list")),
                _tool("coursework", "Coursework", "Materials, assignments and submissions.", "ph-notebook", _action("Open coursework", "admin_coursework_dashboard", primary=True)),
                _tool("attendance", "Attendance & timetable", "Class attendance and lesson schedules.", "ph-calendar-check", _action("Attendance", "admin_attendance_sessions_list", primary=True), _action("Timetable", "admin_timetable_entries_list")),
                _tool("assessments", "Assessments & marks", "Assessments, marks and tabulation.", "ph-exam", _action("Assessments", "admin_assessments_list", primary=True), _action("Mark sheets", "admin_assessments_tabulation")),
                _tool("exams", "Exams", "Exam papers, schedules and results.", "ph-file-text", _action("Open exams", "admin_exams_list", primary=True)),
                _tool("activities", "Clubs & activities", "Clubs, sports, sessions and attendance.", "ph-trophy", _action("Activities", "admin_activities_list", primary=True), _action("Sessions", "admin_activity_sessions")),
            ),
        },
        {
            "name": "Student services",
            "tools": (
                _tool("hostels", "Hostels", "Rooms, beds and student allocations.", "ph-house-line", _action("Hostel allocations", "admin_bed_allocations_list", primary=True)),
                _tool("health", "Health", "Sickbay visits and follow-up.", "ph-first-aid-kit", _action("Open sickbay", "admin_sickbay_dashboard", primary=True)),
                _tool("discipline", "Discipline", "Incidents and learner conduct records.", "ph-gavel", _action("Discipline records", "admin_incidents_list", primary=True)),
                _tool("concerns", "Concerns", "Questions, complaints and follow-up.", "ph-chats-circle", _action("View concerns", "admin_grievances_list", primary=True)),
                _tool("library", "Library", "Books, loans and returns.", "ph-book-bookmark", _action("Open library", "admin_library_books_list", primary=True)),
                _tool("transport", "Transport", "Routes, stops and assignments.", "ph-bus", _action("Transport routes", "admin_transport_routes_list", primary=True)),
                _tool("documents", "Documents", "Files shared with the school community.", "ph-files", _action("Open documents", "admin_documents_list", primary=True)),
            ),
        },
        {
            "name": "Campus management",
            "tools": (
                _tool("finance", "Fees & payments", "Invoices, payments and receipts.", "ph-wallet", _action("Finance dashboard", "admin_finance_dashboard", primary=True), _action("Invoices", "admin_invoices_list")),
                _tool("announcements", "Announcements", "School notices and communication.", "ph-megaphone", _action("Announcements", "admin_announcements_list", primary=True), _action("Communication", "admin_communication_center")),
                _tool("reports", "Reports & analytics", "Campus performance and operational reports.", "ph-chart-bar", _action("Reports", "admin_reports_overview", primary=True), _action("Analytics", "admin_analytics_dashboard")),
                _tool("institutional", "Institutional operations", "Report templates, national results, candidate permits, visitation, meals and learner property.", "ph-buildings", _action("Open institutional centre", "institutional_dashboard", primary=True)),
                _tool("inventory", "Inventory", "School items and stock records.", "ph-package", _action("Open inventory", "admin_inventory_items_list", primary=True)),
            ),
        },
    ),
    "teacher": (
        {
            "name": "Teaching",
            "tools": (
                _tool("timetable", "Timetable", "Today's lessons and teaching schedule.", "ph-calendar", _action("Open timetable", "teacher_timetable", primary=True)),
                _tool("attendance", "Attendance", "Take roll call and review attendance.", "ph-calendar-check", _action("Open attendance", "teacher_attendance_home", primary=True)),
                _tool("coursework", "Coursework", "Materials, assignments, submissions and marking.", "ph-notebook", _action("Open coursework", "teacher_coursework_home", primary=True)),
                _tool("assessments", "Assessments", "Create assessments and enter marks.", "ph-exam", _action("Open assessments", "teacher_assessments_home", primary=True)),
                _tool("exams", "Exams", "Exam papers, attempts and marking.", "ph-file-text", _action("Open exams", "teacher_exams_home", primary=True)),
            ),
        },
        {
            "name": "Learner support",
            "tools": (
                _tool("discipline", "Discipline", "Report and review learner incidents.", "ph-warning-circle", _action("Learner incidents", "teacher_incidents_list", primary=True)),
                _tool("concerns", "Concerns", "Raise a concern or follow up your submissions.", "ph-chats-circle", _action("My concerns", "teacher_grievances_list", primary=True), _action("Raise concern", "teacher_grievances_submit")),
                _tool("announcements", "Announcements", "Read school notices and updates.", "ph-megaphone", _action("View announcements", "teacher_announcements_list", primary=True)),
                _tool("documents", "Documents", "Open files shared with teachers.", "ph-file-doc", _action("View documents", "teacher_documents_list", primary=True)),
            ),
        },
        {
            "name": "Account",
            "tools": (
                _tool("payslips", "Payslips", "View your payroll documents.", "ph-wallet", _action("My payslips", "staff_payslips_list", primary=True)),
                _tool("profile", "Profile & devices", "Update your profile and manage signed-in devices.", "ph-user-circle", _action("My profile", "user_profile", primary=True), _action("My devices", "my_devices")),
            ),
        },
    ),
    "student": (
        {
            "name": "Learning",
            "tools": (
                _tool("timetable", "Timetable", "Your lessons and class schedule.", "ph-calendar", _action("Open timetable", "student_timetable", primary=True)),
                _tool("coursework", "Coursework", "Learning materials, assignments and submissions.", "ph-notebook", _action("Open coursework", "student_coursework_home", primary=True)),
                _tool("results", "Results", "Assessment results and report cards.", "ph-chart-bar", _action("View results", "student_results_home", primary=True), _action("Report card", "student_report_card")),
                _tool("exams", "Exams", "Exam schedules, online papers and results.", "ph-file-text", _action("Exam dashboard", "student_exams_dashboard", primary=True), _action("Exam results", "student_exam_results")),
                _tool("attendance", "Attendance", "Review your attendance record.", "ph-calendar-check", _action("My attendance", "student_attendance_home", primary=True)),
            ),
        },
        {
            "name": "School life",
            "tools": (
                _tool("announcements", "Announcements", "School notices and updates.", "ph-megaphone", _action("View announcements", "student_announcements_list", primary=True)),
                _tool("library", "Library", "Search books and review your loans.", "ph-books", _action("Open library", "student_library_catalog", primary=True)),
                _tool("transport", "Transport", "Your route and transport details.", "ph-bus", _action("My transport", "student_transport_home", primary=True)),
                _tool("boarding", "Boarding", "Your hostel, room and bed information.", "ph-house-line", _action("My boarding", "student_hostel_home", primary=True)),
                _tool("discipline", "Discipline", "Your conduct and incident records.", "ph-warning-circle", _action("My records", "student_incidents_list", primary=True)),
                _tool("health", "Health", "Your sickbay visits and treatment records.", "ph-first-aid-kit", _action("Sickbay visits", "student_sickbay_visits", primary=True)),
            ),
        },
        {
            "name": "Records & account",
            "tools": (
                _tool("fees", "Fees & receipts", "Invoices, balances and payment receipts.", "ph-wallet", _action("View fees", "student_invoices_list", primary=True)),
                _tool("documents", "Documents", "Files shared with students.", "ph-file-doc", _action("View documents", "student_documents_list", primary=True)),
                _tool("id-card", "Student ID", "Open or print your student ID card.", "ph-identification-card", _action("Open ID card", "student_id_card_self", primary=True)),
                _tool("institutional-records", "Verified records", "Candidate readiness, permits, report cards, transcripts and boarding records.", "ph-seal-check", _action("Open verified records", "institutional_my_records", primary=True)),
                _tool("profile", "Profile & devices", "Update your profile and manage signed-in devices.", "ph-user-circle", _action("My profile", "user_profile", primary=True), _action("My devices", "my_devices")),
            ),
        },
    ),
    "parent": (
        {
            "name": "Learning",
            "tools": (
                _tool("coursework", "Coursework", "Learning materials and assignments for your children.", "ph-notebook", _action("View coursework", "parent_coursework_home", primary=True)),
                _tool("results", "Results", "Assessment results and report cards.", "ph-chart-bar", _action("View results", "parent_results_home", primary=True)),
                _tool("exams", "Exams", "Exam results and attempt information.", "ph-file-text", _action("View exams", "parent_exam_results", primary=True)),
                _tool("attendance", "Attendance", "Review attendance for your children.", "ph-calendar-check", _action("View attendance", "parent_attendance_home", primary=True)),
            ),
        },
        {
            "name": "School life",
            "tools": (
                _tool("announcements", "Announcements", "School notices and updates.", "ph-megaphone", _action("View announcements", "parent_announcements_list", primary=True)),
                _tool("discipline", "Discipline", "Conduct and incident records.", "ph-warning-circle", _action("View discipline", "parent_incidents_list", primary=True)),
                _tool("health", "Health", "Sickbay visits and treatment records.", "ph-first-aid-kit", _action("Sickbay visits", "parent_sickbay_visits", primary=True)),
                _tool("transport", "Transport", "Routes and transport details.", "ph-bus", _action("View transport", "parent_transport_home", primary=True)),
                _tool("library", "Library", "Books currently borrowed by your children.", "ph-books", _action("Library loans", "parent_library_loans", primary=True)),
                _tool("boarding", "Boarding", "Hostel, room and bed information.", "ph-house-line", _action("View boarding", "parent_hostel_home", primary=True)),
            ),
        },
        {
            "name": "Support & records",
            "tools": (
                _tool("concerns", "Concerns", "Raise a concern and follow its progress.", "ph-chats-circle", _action("My concerns", "parent_grievances_list", primary=True), _action("Raise concern", "parent_grievances_submit")),
                _tool("documents", "Documents", "Files shared with parents and guardians.", "ph-file-doc", _action("View documents", "parent_documents_list", primary=True)),
                _tool("fees", "Fees & payments", "Invoices, balances, payments and receipts.", "ph-wallet", _action("View fees", "parent_invoices_list", primary=True)),
                _tool("institutional-records", "Verified learner records", "Candidate readiness, permits, reports, transcripts, visits, meals and property records.", "ph-seal-check", _action("Open learner records", "institutional_my_records", primary=True)),
            ),
        },
        {
            "name": "Account",
            "tools": (
                _tool("results-pin", "Results PIN", "Protect access to published results.", "ph-key", _action("Manage PIN", "parent_results_pin_security", primary=True)),
                _tool("messages", "Message preferences", "Choose how the school contacts you.", "ph-bell", _action("Message preferences", "parent_communication_preferences", primary=True)),
                _tool("digests", "Weekly summaries", "Review school summaries sent to you.", "ph-newspaper", _action("View summaries", "parent_digest_history", primary=True)),
                _tool("profile", "Profile & devices", "Update your profile and manage signed-in devices.", "ph-user-circle", _action("My profile", "user_profile", primary=True), _action("My devices", "my_devices")),
            ),
        },
    ),
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


def build_capability_context(user, *, role: str | None = None):
    role = role or portal_role(user)
    meta = ROLE_META.get(role, ROLE_META["student"])
    groups = []
    all_tools = []

    for group_spec in ROLE_TOOL_GROUPS.get(role, ()):
        tools = []
        for tool_spec in group_spec["tools"]:
            actions = []
            for action_spec in tool_spec["actions"]:
                url = _safe_reverse(action_spec["route"])
                if not url:
                    continue
                actions.append(
                    {
                        "label": action_spec["label"],
                        "url": url,
                        "primary": action_spec["primary"],
                    }
                )
            if not actions:
                continue

            tool = {
                "key": tool_spec["key"],
                "title": tool_spec["title"],
                "summary": tool_spec["summary"],
                "icon": tool_spec["icon"],
                "actions": actions,
                "search_text": " ".join(
                    [
                        group_spec["name"],
                        tool_spec["title"],
                        tool_spec["summary"],
                        *[action["label"] for action in actions],
                    ]
                ).lower(),
            }
            tools.append(tool)
            all_tools.append(tool)

        if tools:
            groups.append({"name": group_spec["name"], "tools": tools})

    return {
        "capability_role": role,
        "capability_role_label": meta["label"],
        "capability_page_title": meta["title"],
        "capability_intro": meta["intro"],
        "capability_groups": groups,
        "capability_tools": all_tools,
        "capability_tool_count": len(all_tools),
        "capability_action_count": sum(len(tool["actions"]) for tool in all_tools),
        "capability_is_full_admin": role == "admin",
        "capability_is_campus_admin": role == "campus_admin",
    }
