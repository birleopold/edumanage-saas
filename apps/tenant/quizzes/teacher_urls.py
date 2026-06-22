from django.urls import path

from . import portal_views

urlpatterns = [
    path("", portal_views.teacher_quiz_list, name="teacher_quiz_list"),
    path("create/", portal_views.quiz_create, name="teacher_quiz_create"),
    path("<int:pk>/", portal_views.quiz_detail, name="teacher_quiz_detail"),
    path("<int:pk>/edit/", portal_views.quiz_edit, name="teacher_quiz_edit"),
    path("<int:pk>/publish-toggle/", portal_views.quiz_toggle_publish, name="teacher_quiz_publish_toggle"),
    path("<int:quiz_pk>/questions/add/", portal_views.question_create, name="teacher_quiz_question_add"),
    path("questions/<int:question_pk>/choices/add/", portal_views.choice_create, name="teacher_quiz_choice_add"),
    path("attempts/<int:pk>/", portal_views.attempt_detail, name="teacher_quiz_attempt_detail"),
    path("answers/<int:pk>/grade/", portal_views.grade_answer, name="teacher_quiz_grade_answer"),
]
