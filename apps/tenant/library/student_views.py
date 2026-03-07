from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Book, BookCopy, BookLoan, Fine, Reservation


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.STUDENT)
def book_catalog(request):
    student = StudentProfile.objects.filter(user=request.user).first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    q = (request.GET.get("q") or "").strip()
    category_filter = request.GET.get("category", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Book.objects.prefetch_related("authors").select_related("category").filter(is_active=True)
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(isbn__icontains=q) | Q(authors__name__icontains=q) | Q(description__icontains=q)
        ).distinct()
    if category_filter:
        qs = qs.filter(category_id=category_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    # Get categories for filter
    from .models import Category
    categories = Category.objects.filter(is_active=True).order_by("name")

    return render(
        request,
        "portals/student/library/catalog.html",
        {
            "student": student,
            "books": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "categories": categories,
            "category_filter": category_filter,
        },
    )


@role_required(Role.STUDENT)
def book_detail(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    book = get_object_or_404(Book.objects.prefetch_related("authors", "copies"), pk=pk)
    
    # Check if student has active reservation
    has_reservation = Reservation.objects.filter(
        book=book,
        student=student,
        status=Reservation.PENDING
    ).exists()

    return render(
        request,
        "portals/student/library/book_detail.html",
        {"student": student, "book": book, "has_reservation": has_reservation},
    )


@role_required(Role.STUDENT)
def reserve_book(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    book = get_object_or_404(Book, pk=pk)

    # Check if already reserved
    if Reservation.objects.filter(book=book, student=student, status=Reservation.PENDING).exists():
        messages.warning(request, "You already have a pending reservation for this book.")
    else:
        # Create reservation
        Reservation.objects.create(
            book=book,
            borrower_type=Reservation.BORROWER_TYPE_STUDENT,
            student=student,
            status=Reservation.PENDING,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        messages.success(request, f"Book '{book.title}' reserved successfully.")

    return redirect("student_library_book_detail", pk=pk)


@role_required(Role.STUDENT)
def my_loans(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = BookLoan.objects.select_related("copy", "copy__book").prefetch_related("copy__book__authors").filter(
        student=student, borrower_type=BookLoan.BORROWER_TYPE_STUDENT
    ).order_by("-borrowed_at")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/student/library/loans_list.html",
        {"student": student, "loans": page_obj.object_list, "page_obj": page_obj, "per_page": per_page},
    )


@role_required(Role.STUDENT)
def my_reservations(request):
    student = StudentProfile.objects.filter(user=request.user).first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    reservations = Reservation.objects.select_related("book").filter(
        student=student, borrower_type=Reservation.BORROWER_TYPE_STUDENT
    ).order_by("-reserved_at")

    return render(
        request,
        "portals/student/library/reservations_list.html",
        {"student": student, "reservations": reservations},
    )


@role_required(Role.STUDENT)
def my_fines(request):
    student = StudentProfile.objects.filter(user=request.user).first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    fines = Fine.objects.select_related("loan", "loan__copy", "loan__copy__book").filter(
        student=student, borrower_type=Fine.BORROWER_TYPE_STUDENT
    ).order_by("-issued_at")

    total_unpaid = sum(f.amount for f in fines if f.status == Fine.UNPAID)

    return render(
        request,
        "portals/student/library/fines_list.html",
        {"student": student, "fines": fines, "total_unpaid": total_unpaid},
    )
