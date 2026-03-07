from django.urls import path

from . import admin_views

urlpatterns = [
    # Books
    path("", admin_views.book_list, name="admin_library_books_list"),
    path("books/create/", admin_views.book_create, name="admin_library_book_create"),
    path("books/<int:pk>/edit/", admin_views.book_edit, name="admin_library_book_edit"),
    # Categories
    path("categories/", admin_views.category_list, name="admin_library_categories_list"),
    path("categories/create/", admin_views.category_create, name="admin_library_category_create"),
    path("categories/<int:pk>/edit/", admin_views.category_edit, name="admin_library_category_edit"),
    # Authors
    path("authors/", admin_views.author_list, name="admin_library_authors_list"),
    path("authors/create/", admin_views.author_create, name="admin_library_author_create"),
    path("authors/<int:pk>/edit/", admin_views.author_edit, name="admin_library_author_edit"),
    # Book Copies
    path("copies/", admin_views.copy_list, name="admin_library_copies_list"),
    path("copies/create/", admin_views.copy_create, name="admin_library_copy_create"),
    path("copies/<int:pk>/edit/", admin_views.copy_edit, name="admin_library_copy_edit"),
    # Loans/Checkout
    path("loans/", admin_views.loan_list, name="admin_library_loans_list"),
    path("loans/create/", admin_views.loan_create, name="admin_library_loan_create"),
    path("loans/<int:pk>/edit/", admin_views.loan_edit, name="admin_library_loan_edit"),
    path("loans/<int:pk>/mark-returned/", admin_views.loan_mark_returned, name="admin_library_loan_mark_returned"),
    # Check-in with Barcode
    path("checkin/", admin_views.checkin, name="admin_library_checkin"),
    # Reservations
    path("reservations/", admin_views.reservation_list, name="admin_library_reservations_list"),
    # Fines
    path("fines/", admin_views.fine_list, name="admin_library_fines_list"),
    path("fines/<int:pk>/mark-paid/", admin_views.fine_mark_paid, name="admin_library_fine_mark_paid"),
    path("fines/<int:pk>/waive/", admin_views.fine_waive, name="admin_library_fine_waive"),
]
