from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.book_catalog, name="student_library_catalog"),
    path("books/<int:pk>/", student_views.book_detail, name="student_library_book_detail"),
    path("books/<int:pk>/reserve/", student_views.reserve_book, name="student_library_reserve_book"),
    path("my-loans/", student_views.my_loans, name="student_library_loans"),
    path("my-reservations/", student_views.my_reservations, name="student_library_reservations"),
    path("my-fines/", student_views.my_fines, name="student_library_fines"),
]
