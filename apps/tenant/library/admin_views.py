from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import BookCopyForm, BookForm, BookLoanForm
from .models import Book, BookCopy, BookLoan


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

    qs = Book.objects.all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(isbn__icontains=q))

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
        form = BookForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_library_books_list")
    else:
        form = BookForm()

    return render(request, "portals/admin/library/book_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def book_edit(request, pk: int):
    obj = get_object_or_404(Book, pk=pk)

    if request.method == "POST":
        form = BookForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
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

    qs = BookCopy.objects.select_related("book").all()
    if q:
        qs = qs.filter(Q(copy_code__icontains=q) | Q(book__title__icontains=q) | Q(book__author__icontains=q))

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

    qs = BookLoan.objects.select_related("copy", "copy__book", "student").all()
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
            form.save()
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
        if loan.returned_at is None:
            loan.returned_at = timezone.localdate()
        loan.save(update_fields=["status", "returned_at"])
        messages.success(request, "Loan marked as returned.")

    return redirect("admin_library_loans_list")
