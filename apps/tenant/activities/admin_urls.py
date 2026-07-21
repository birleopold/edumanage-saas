from django.urls import path

from . import admin_views, programme_views

urlpatterns = [
    path("", admin_views.activity_list, name="admin_activities_list"),
    path("create/", admin_views.activity_create, name="admin_activities_create"),
    path("<int:pk>/edit/", admin_views.activity_edit, name="admin_activities_edit"),
    path("<int:pk>/members/", admin_views.activity_members, name="admin_activities_members"),
    path("<int:pk>/members/add/", admin_views.activity_member_add, name="admin_activities_member_add"),
    path(
        "<int:pk>/members/<int:member_id>/remove/",
        admin_views.activity_member_remove,
        name="admin_activities_member_remove",
    ),

    path("programme/", programme_views.programme_dashboard, name="admin_activity_programme_dashboard"),
    path("programme/<int:activity_pk>/", programme_views.programme_edit, name="admin_activity_programme_edit"),
    path("programme/<int:activity_pk>/groups/create/", programme_views.group_create, name="admin_activity_group_create"),
    path("programme/groups/<int:pk>/edit/", programme_views.group_edit, name="admin_activity_group_edit"),
    path("programme/participation/<int:member_pk>/", programme_views.participation_edit, name="admin_activity_participation_edit"),
    path("programme/sessions/", programme_views.session_list, name="admin_activity_sessions"),
    path("programme/sessions/create/", programme_views.session_create, name="admin_activity_session_create"),
    path("programme/sessions/<int:pk>/", programme_views.session_detail, name="admin_activity_session_detail"),
    path("programme/achievements/create/", programme_views.achievement_create, name="admin_activity_achievement_create"),
    path("programme/learners/<int:student_pk>/", programme_views.learner_summary, name="admin_activity_learner_summary"),
]
