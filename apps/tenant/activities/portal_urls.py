from django.urls import path

from . import engagement_views

urlpatterns = [
    path(
        "",
        engagement_views.learner_activity_dashboard,
        name="activities_learner_dashboard",
    ),
    path(
        "learners/<int:student_id>/",
        engagement_views.learner_activity_dashboard,
        name="activities_learner_dashboard_for_student",
    ),
    path(
        "incidents/new/",
        engagement_views.incident_create,
        name="activities_incident_create",
    ),
    path(
        "achievements/<int:achievement_id>/certificate/issue/",
        engagement_views.certificate_issue,
        name="activities_certificate_issue",
    ),
    path(
        "certificates/<int:pk>.pdf",
        engagement_views.certificate_download,
        name="activities_certificate_pdf",
    ),
    path(
        "certificates/verify/<str:token>/",
        engagement_views.verify_certificate,
        name="activities_certificate_verify",
    ),
]
