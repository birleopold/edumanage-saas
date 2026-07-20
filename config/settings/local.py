from .base import *


DEBUG = True

INSTALLED_APPS = [
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
    "apps.tenant.education_frameworks",
    "apps.tenant.attendance",
    "apps.tenant.assessments",
    "apps.tenant.finance",
    "apps.tenant.announcements",
    "apps.tenant.coursework",
    "apps.tenant.activities",
    "apps.tenant.duty",
    "apps.tenant.timetable",
    "apps.tenant.discipline",
    "apps.tenant.sickbay",
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
TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"
SHARED_APPS = tuple(app for app in INSTALLED_APPS if not app.startswith("apps.tenant."))
TENANT_APPS = tuple(app for app in INSTALLED_APPS if app.startswith("apps.tenant."))
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
