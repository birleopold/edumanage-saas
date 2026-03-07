from decouple import config

from .base import *


SHARED_APPS = (
    "django_tenants",
    "apps.public.tenants",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
)

TENANT_APPS = (
    "apps.core",
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
)

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    *MIDDLEWARE,
]

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": config("POSTGRES_DB", default="edumanage_saas"),
        "USER": config("POSTGRES_USER", default="postgres"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="postgres"),
        "HOST": config("POSTGRES_HOST", default="127.0.0.1"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"

AUTH_USER_MODEL = "users.User"
