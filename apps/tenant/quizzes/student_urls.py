from django.urls import path

from . import portal_views

urlpatterns = [
    path("", portal_views.student_quiz_list, name="student_quiz_list"),
    path("<int:pk>/take/", portal_views.student_take_quiz, name="student_quiz_take"),
    path("attempts/<int:pk>/result/", portal_views.student_quiz_result, name="student_quiz_result"),
]
