from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import FeeItemForm, InvoiceForm, InvoiceLineForm, PaymentForm
from .models import FeeItem, Invoice, InvoiceLine, Payment


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _selected_campus_id(request):
    current = get_current_campus(request)
    if "campus" in request.GET:
        raw = request.GET.get("campus")
        if raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return current.id if current else None


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
def fee_item_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = FeeItem.objects.all()
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/finance/fee_items_list.html",
        {"items": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def fee_item_create(request):
    if request.method == "POST":
        form = FeeItemForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_fee_items_list")
    else:
        form = FeeItemForm()
    return render(request, "portals/admin/finance/fee_item_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def fee_item_edit(request, pk: int):
    obj = get_object_or_404(FeeItem, pk=pk)
    if request.method == "POST":
        form = FeeItemForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_fee_items_list")
    else:
        form = FeeItemForm(instance=obj)
    return render(
        request,
        "portals/admin/finance/fee_item_form.html",
        {"form": form, "mode": "edit", "item": obj},
    )


@role_required(Role.ADMIN)
def invoice_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)

    qs = Invoice.objects.select_related(
        "student",
        "academic_year",
        "academic_term",
    ).prefetch_related("lines", "payments")

    if campus_id:
        qs = qs.filter(student__campus_id=campus_id)

    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(reference__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/finance/invoices_list.html",
        {
            "invoices": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@role_required(Role.ADMIN)
def invoice_create(request):
    current = get_current_campus(request)
    if request.method == "POST":
        form = InvoiceForm(request.POST, campus=current)
        if form.is_valid():
            invoice = form.save()
            return redirect("admin_invoices_detail", pk=invoice.pk)
    else:
        form = InvoiceForm(campus=current)
    return render(request, "portals/admin/finance/invoice_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def invoice_edit(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    campus = getattr(invoice.student, "campus", None)
    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice, campus=campus)
        if form.is_valid():
            form.save()
            return redirect("admin_invoices_detail", pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice, campus=campus)
    return render(
        request,
        "portals/admin/finance/invoice_form.html",
        {"form": form, "mode": "edit", "invoice": invoice},
    )


@role_required(Role.ADMIN)
def invoice_detail(request, pk: int):
    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term")
        .prefetch_related("lines", "payments"),
        pk=pk,
    )

    line_form = InvoiceLineForm()
    payment_form = PaymentForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_line":
            line_form = InvoiceLineForm(request.POST)
            if line_form.is_valid():
                line = line_form.save(commit=False)
                line.invoice = invoice
                if line.fee_item and (not line.description):
                    line.description = line.fee_item.name
                line.save()
                return redirect("admin_invoices_detail", pk=invoice.pk)
        elif action == "add_payment":
            payment_form = PaymentForm(request.POST)
            if payment_form.is_valid():
                payment = payment_form.save(commit=False)
                payment.invoice = invoice
                payment.save()
                return redirect("admin_invoices_detail", pk=invoice.pk)
        else:
            messages.error(request, "Invalid action.")

    total_amount = invoice.total_amount()
    total_paid = invoice.total_paid()
    balance = invoice.balance()

    return render(
        request,
        "portals/admin/finance/invoice_detail.html",
        {
            "invoice": invoice,
            "line_form": line_form,
            "payment_form": payment_form,
            "total_amount": total_amount,
            "total_paid": total_paid,
            "balance": balance,
        },
    )


@role_required(Role.ADMIN)
def invoice_line_remove(request, pk: int, line_id: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    line = get_object_or_404(InvoiceLine, pk=line_id, invoice=invoice)
    if request.method == "POST":
        line.delete()
    return redirect("admin_invoices_detail", pk=invoice.pk)


@role_required(Role.ADMIN)
def invoice_payment_remove(request, pk: int, payment_id: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    payment = get_object_or_404(Payment, pk=payment_id, invoice=invoice)
    if request.method == "POST":
        payment.delete()
    return redirect("admin_invoices_detail", pk=invoice.pk)
