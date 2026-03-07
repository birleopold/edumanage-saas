from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import AuthorForm, BookCopyForm, BookForm, BookLoanForm, CategoryForm, CheckInForm, FineForm, ReservationForm
from .models import Author, Book, BookCopy, BookLoan, Category, Fine, Reservation


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.ADMIN)
def book_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Book.objects.prefetch_related("authors").select_related("category").all()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(isbn__icontains=q) | Q(authors__name__icontains=q) | Q(category__name__icontains=q)
        ).distinct()

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/library/books_list.html",
        {"books": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def book_create(request):
    if request.method == "POST":
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Book created successfully.")
            return redirect("admin_library_books_list")
    else:
        form = BookForm()

    return render(request, "portals/admin/library/book_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def book_edit(request, pk: int):
    obj = get_object_or_404(Book, pk=pk)

    if request.method == "POST":
        form = BookForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Book updated successfully.")
            return redirect("admin_library_books_list")
    else:
        form = BookForm(instance=obj)

    return render(
        request,
        "portals/admin/library/book_form.html",
        {"form": form, "mode": "edit", "book": obj},
    )


@role_required(Role.ADMIN)
def copy_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = BookCopy.objects.select_related("book").prefetch_related("book__authors").all()
    if q:
        qs = qs.filter(
            Q(copy_code__icontains=q) | Q(barcode__icontains=q) | Q(book__title__icontains=q) | Q(book__authors__name__icontains=q)
        ).distinct()

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/library/copies_list.html",
        {"copies": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def copy_create(request):
    if request.method == "POST":
        form = BookCopyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Book copy created successfully.")
            return redirect("admin_library_copies_list")
    else:
        form = BookCopyForm()

    return render(request, "portals/admin/library/copy_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def copy_edit(request, pk: int):
    obj = get_object_or_404(BookCopy, pk=pk)

    if request.method == "POST":
        form = BookCopyForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Book copy updated successfully.")
            return redirect("admin_library_copies_list")
    else:
        form = BookCopyForm(instance=obj)

    return render(
        request,
        "portals/admin/library/copy_form.html",
        {"form": form, "mode": "edit", "copy": obj},
    )


@role_required(Role.ADMIN)
def loan_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = BookLoan.objects.select_related("copy", "copy__book", "student", "staff").all()
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(copy__copy_code__icontains=q)
            | Q(copy__book__title__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/library/loans_list.html",
        {"loans": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def loan_create(request):
    if request.method == "POST":
        form = BookLoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.checked_out_by = request.user
            loan.save()
            form.save_m2m()
            
            # Update copy status
            loan.copy.status = BookCopy.CHECKED_OUT
            loan.copy.save(update_fields=["status"])
            
            messages.success(request, f"Book checked out successfully to {loan.student or loan.staff}.")
            return redirect("admin_library_loans_list")
    else:
        form = BookLoanForm()

    return render(request, "portals/admin/library/loan_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def loan_edit(request, pk: int):
    obj = get_object_or_404(BookLoan, pk=pk)

    if request.method == "POST":
        form = BookLoanForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Loan updated successfully.")
            return redirect("admin_library_loans_list")
    else:
        form = BookLoanForm(instance=obj)

    return render(
        request,
        "portals/admin/library/loan_form.html",
        {"form": form, "mode": "edit", "loan": obj},
    )


@role_required(Role.ADMIN)
def loan_mark_returned(request, pk: int):
    loan = get_object_or_404(BookLoan, pk=pk)

    if request.method == "POST":
        loan.status = BookLoan.RETURNED
        loan.returned_at = timezone.localdate()
        loan.checked_in_by = request.user
        loan.save(update_fields=["status", "returned_at", "checked_in_by"])
        
        # Update copy status back to available
        loan.copy.status = BookCopy.AVAILABLE
        loan.copy.save(update_fields=["status"])
        
        # Check if there's an overdue fine
        if loan.is_overdue():
            fine_amount = loan.calculate_fine()
            Fine.objects.create(
                loan=loan,
                borrower_type=loan.borrower_type,
                student=loan.student,
                staff=loan.staff,
                amount=fine_amount,
                reason=f"Overdue return: {loan.days_overdue()} days late",
                status=Fine.UNPAID,
            )
            messages.warning(request, f"Book returned. Overdue fine of {fine_amount} applied.")
        else:
            messages.success(request, "Book returned successfully.")

    return redirect("admin_library_loans_list")


# Category Views
@role_required(Role.ADMIN)
def category_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Category.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/library/categories_list.html",
        {"categories": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created successfully.")
            return redirect("admin_library_categories_list")
    else:
        form = CategoryForm()

    return render(request, "portals/admin/library/category_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def category_edit(request, pk: int):
    obj = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated successfully.")
            return redirect("admin_library_categories_list")
    else:
        form = CategoryForm(instance=obj)

    return render(request, "portals/admin/library/category_form.html", {"form": form, "mode": "edit", "category": obj})


# Author Views
@role_required(Role.ADMIN)
def author_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Author.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/library/authors_list.html",
        {"authors": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def author_create(request):
    if request.method == "POST":
        form = AuthorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Author created successfully.")
            return redirect("admin_library_authors_list")
    else:
        form = AuthorForm()

    return render(request, "portals/admin/library/author_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def author_edit(request, pk: int):
    obj = get_object_or_404(Author, pk=pk)

    if request.method == "POST":
        form = AuthorForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Author updated successfully.")
            return redirect("admin_library_authors_list")
    else:
        form = AuthorForm(instance=obj)

    return render(request, "portals/admin/library/author_form.html", {"form": form, "mode": "edit", "author": obj})


# Check-in with Barcode
@role_required(Role.ADMIN)
def checkin(request):
    if request.method == "POST":
        form = CheckInForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["copy_code_or_barcode"]
            
            # Try to find the book copy by code or barcode
            copy = BookCopy.objects.filter(Q(copy_code=code) | Q(barcode=code)).first()
            
            if not copy:
                messages.error(request, f"No book copy found with code/barcode: {code}")
            else:
                # Find active loan for this copy
                loan = BookLoan.objects.filter(copy=copy, status=BookLoan.OPEN).first()
                
                if not loan:
                    messages.warning(request, f"No active loan found for {copy}.")
                else:
                    # Mark as returned
                    loan.status = BookLoan.RETURNED
                    loan.returned_at = timezone.localdate()
                    loan.checked_in_by = request.user
                    loan.save()
                    
                    copy.status = BookCopy.AVAILABLE
                    copy.save(update_fields=["status"])
                    
                    # Handle fines
                    if loan.is_overdue():
                        fine_amount = loan.calculate_fine()
                        Fine.objects.create(
                            loan=loan,
                            borrower_type=loan.borrower_type,
                            student=loan.student,
                            staff=loan.staff,
                            amount=fine_amount,
                            reason=f"Overdue return: {loan.days_overdue()} days late",
                        )
                        messages.warning(request, f"Checked in {copy.book.title}. Fine of {fine_amount} applied for {loan.days_overdue()} days overdue.")
                    else:
                        messages.success(request, f"Checked in {copy.book.title} successfully.")
                    
                    return redirect("admin_library_checkin")
    else:
        form = CheckInForm()

    return render(request, "portals/admin/library/checkin.html", {"form": form})


# Reservation Views
@role_required(Role.ADMIN)
def reservation_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Reservation.objects.select_related("book", "student", "staff").all()
    if q:
        qs = qs.filter(
            Q(book__title__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(staff__first_name__icontains=q)
            | Q(staff__last_name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/library/reservations_list.html",
        {"reservations": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


# Fine Views
@role_required(Role.ADMIN)
def fine_list(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = request.GET.get("status", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Fine.objects.select_related("loan", "student", "staff", "waived_by").all()
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(staff__first_name__icontains=q)
            | Q(staff__last_name__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/library/fines_list.html",
        {"fines": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page, "status_filter": status_filter},
    )


@role_required(Role.ADMIN)
def fine_mark_paid(request, pk: int):
    fine = get_object_or_404(Fine, pk=pk)

    if request.method == "POST":
        fine.status = Fine.PAID
        fine.paid_at = timezone.now()
        fine.save()
        messages.success(request, "Fine marked as paid.")

    return redirect("admin_library_fines_list")


@role_required(Role.ADMIN)
def fine_waive(request, pk: int):
    fine = get_object_or_404(Fine, pk=pk)

    if request.method == "POST":
        fine.status = Fine.WAIVED
        fine.waived_at = timezone.now()
        fine.waived_by = request.user
        fine.save()
        messages.success(request, "Fine waived.")

    return redirect("admin_library_fines_list")
