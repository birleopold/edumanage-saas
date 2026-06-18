from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.services import (
    campus_queryset,
    get_or_create_organization,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .invoicing import attach_invoice_amounts, collection_summary, invoice_amounts
from .models import Invoice, MobilePaymentRequest, Payment
from .payment_forms import ParentPaymentInitiationForm
from .payment_gateway import initiate_collection
from .pdf_receipt import generate_payment_receipt_pdf


def _parent_student_ids(request):
    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return None, []
    update_current_campus_from_request(request)
    campus_id = selected_campus_id_from_request(request)
    links_qs = ParentStudentLink.objects.filter(parent=parent).select_related("student")
    if campus_id:
        links_qs = links_qs.filter(student__campus_id=campus_id)
    return parent, list(links_qs.values_list("student_id", flat=True))


@role_required(Role.PARENT)
def invoice_list(request):
    parent, student_ids = _parent_student_ids(request)
    if parent is None:
        return HttpResponseForbidden("No parent profile linked to this account.")
    campuses = campus_queryset()
    campus_id = selected_campus_id_from_request(request)
    status = (request.GET.get("status") or "").strip().upper()
    student_filter = (request.GET.get("student") or "").strip()
    page_number = request.GET.get("page") or 1
    links_qs = ParentStudentLink.objects.filter(parent=parent).select_related("student", "student__campus")
    if campus_id:
        links_qs = links_qs.filter(student__campus_id=campus_id)
    qs = Invoice.objects.filter(student_id__in=student_ids).select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments").order_by("student__last_name", "student__first_name", "-created_at")
    if student_filter:
        try:
            sid = int(student_filter)
        except (TypeError, ValueError):
            sid = None
        if sid in student_ids:
            qs = qs.filter(student_id=sid)
    invoices_all = attach_invoice_amounts(list(qs))
    invoices_filtered = [inv for inv in invoices_all if inv.display_status == status] if status else invoices_all
    page_obj = Paginator(invoices_filtered, 25).get_page(page_number)
    return render(request, "portals/parent/finance/invoices_list.html", {"parent": parent, "invoices": page_obj.object_list, "page_obj": page_obj, "summary": collection_summary(invoices_all), "campuses": campuses, "links": links_qs, "selected_campus_id": campus_id, "selected_student_id": int(student_filter) if student_filter.isdigit() else None, "status": status, "status_options": ["PAID", "PARTIAL", "OVERDUE", "UNPAID", "CLOSED"]})


@role_required(Role.PARENT)
def invoice_detail(request, pk: int):
    parent, student_ids = _parent_student_ids(request)
    if parent is None:
        return HttpResponseForbidden("No parent profile linked to this account.")
    if not student_ids:
        raise Http404("No linked students for this filter.")
    invoice = get_object_or_404(Invoice.objects.select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments", "mobile_payment_requests"), pk=pk, student_id__in=student_ids)
    amounts = invoice_amounts(invoice)
    return render(request, "portals/parent/finance/invoice_detail.html", {"parent": parent, "invoice": invoice, "total_amount": amounts.total_amount, "subtotal_lines": amounts.subtotal_lines, "total_paid": amounts.total_paid, "balance": amounts.balance, "display_status": amounts.display_status, "is_overdue": amounts.is_overdue, "payment_requests": invoice.mobile_payment_requests.all()[:10]})


@role_required(Role.PARENT)
def initiate_payment(request, pk: int):
    parent, student_ids = _parent_student_ids(request)
    if parent is None:
        return HttpResponseForbidden("No parent profile linked to this account.")
    if not student_ids:
        raise Http404("No linked students for this filter.")
    invoice = get_object_or_404(Invoice.objects.select_related("student").prefetch_related("lines", "payments"), pk=pk, student_id__in=student_ids)
    balance = invoice_amounts(invoice).balance
    initial = {"amount": balance, "phone_number": parent.phone or "", "network": Payment.MTN_MOMO}
    form = ParentPaymentInitiationForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            payment_request = initiate_collection(invoice=invoice, amount=form.cleaned_data["amount"], phone_number=form.cleaned_data["phone_number"], network=form.cleaned_data["network"], requested_by=request.user)
            messages.success(request, f"Payment request submitted. Status: {payment_request.status}.")
            return redirect("parent_invoices_detail", pk=invoice.pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "portals/parent/finance/payment_initiate.html", {"parent": parent, "invoice": invoice, "balance": balance, "form": form})


@role_required(Role.PARENT)
def payment_receipt_pdf(request, pk: int, payment_id: int):
    parent, student_ids = _parent_student_ids(request)
    if parent is None:
        return HttpResponseForbidden("No parent profile linked to this account.")
    if not student_ids:
        raise Http404("No linked students for this filter.")
    payment = get_object_or_404(Payment.objects.select_related("invoice", "invoice__student"), pk=payment_id, invoice_id=pk, invoice__student_id__in=student_ids)
    org = get_or_create_organization()
    st = payment.invoice.student
    buf = generate_payment_receipt_pdf(payment=payment, org=org, student_label=str(st))
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="receipt_payment_{payment.pk}.pdf"'
    return response


@role_required(Role.PARENT)
def invoice_print(request, pk: int):
    parent, student_ids = _parent_student_ids(request)
    if parent is None:
        return HttpResponseForbidden("No parent profile linked to this account.")
    if not student_ids:
        raise Http404("No linked students for this filter.")
    invoice = get_object_or_404(Invoice.objects.select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments"), pk=pk, student_id__in=student_ids)
    amounts = invoice_amounts(invoice)
    org = get_or_create_organization()
    return render(request, "portals/parent/finance/invoice_print.html", {"parent": parent, "invoice": invoice, "org": org, "total_amount": amounts.total_amount, "subtotal_lines": amounts.subtotal_lines, "total_paid": amounts.total_paid, "balance": amounts.balance})
