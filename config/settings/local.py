from .base import *


DEBUG = True

INSTALLED_APPS = [
    "django_tenants",
    "apps.public.tenants",
    *INSTALLED_APPS,
]

INSTALLED_APPS += [
    "apps.tenant.users",
    "apps.tenant.portals",
    "apps.tenant.students",
    "apps.tenant.teachers",
    "apps.tenant.parents",
    "apps.tenant.academics",
    "apps.tenant.attendance",
    "apps.tenant.assessments",
    "apps.tenant.finance",
    "apps.tenant.announcements",
    "apps.tenant.coursework",
    "apps.tenant.activities",
    "apps.tenant.duty",
    "apps.tenant.timetable",
    "apps.tenant.discipline",
    "apps.tenant.documents",
    "apps.tenant.transport",
    "apps.tenant.library",
    "apps.tenant.hostels",
    "apps.tenant.inventory",
    "apps.tenant.exams",
    "apps.tenant.reports",
    "apps.tenant.orgsettings",
    "apps.tenant.admissions",
    "apps.tenant.hr",
    "apps.tenant.quizzes",
    "apps.tenant.polls",
    "apps.tenant.messaging",
    "apps.tenant.grievances",
    "apps.tenant.audit",
]

AUTH_USER_MODEL = "users.User"
