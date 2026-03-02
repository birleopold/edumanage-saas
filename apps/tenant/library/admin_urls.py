from django.urls import path

from . import admin_views

urlpatterns = [
    path("books/", admin_views.book_list, name="admin_library_books_list"),
    path("books/create/", admin_views.book_create, name="admin_library_books_create"),
    path("books/<int:pk>/edit/", admin_views.book_edit, name="admin_library_books_edit"),

    path("copies/", admin_views.copy_list, name="admin_library_copies_list"),
    path("copies/create/", admin_views.copy_create, name="admin_library_copies_create"),
    path("copies/<int:pk>/edit/", admin_views.copy_edit, name="admin_library_copies_edit"),

    path("loans/", admin_views.loan_list, name="admin_library_loans_list"),
    path("loans/create/", admin_views.loan_create, name="admin_library_loans_create"),
    path("loans/<int:pk>/edit/", admin_views.loan_edit, name="admin_library_loans_edit"),
    path("loans/<int:pk>/return/", admin_views.loan_mark_returned, name="admin_library_loans_return"),
]
