from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .invoicing import attach_invoice_amounts, collection_summary, invoice_amounts
from .models import Invoice, Payment
from .pdf_receipt import generate_payment_receipt_pdf


@role_required(Role.STUDENT)
def invoice_list(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    status = (request.GET.get("status") or "").strip().upper()
    page_number = request.GET.get("page") or 1

    qs = Invoice.objects.filter(student=student).select_related("academic_year", "academic_term").prefetch_related("lines", "payments")
    invoices_all = attach_invoice_amounts(list(qs.order_by("-created_at")))

    if status:
        invoices_filtered = [inv for inv in invoices_all if inv.display_status == status]
    else:
        invoices_filtered = invoices_all

    paginator = Paginator(invoices_filtered, 20)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/student/finance/invoices_list.html",
        {
            "student": student,
            "invoices": page_obj.object_list,
            "page_obj": page_obj,
            "summary": collection_summary(invoices_all),
            "status": status,
            "status_options": ["PAID", "PARTIAL", "OVERDUE", "UNPAID", "CLOSED"],
        },
    )


@role_required(Role.STUDENT)
def invoice_detail(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term")
        .prefetch_related("lines", "payments"),
        pk=pk,
        student=student,
    )
    amounts = invoice_amounts(invoice)

    return render(
        request,
        "portals/student/finance/invoice_detail.html",
        {
            "student": student,
            "invoice": invoice,
            "total_amount": amounts.total_amount,
            "subtotal_lines": amounts.subtotal_lines,
            "total_paid": amounts.total_paid,
            "balance": amounts.balance,
            "display_status": amounts.display_status,
            "is_overdue": amounts.is_overdue,
        },
    )


@role_required(Role.STUDENT)
def payment_receipt_pdf(request, pk: int, payment_id: int):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    payment = get_object_or_404(
        Payment.objects.select_related("invoice", "invoice__student"),
        pk=payment_id,
        invoice_id=pk,
        invoice__student=student,
    )
    org = get_or_create_organization()
    buf = generate_payment_receipt_pdf(payment=payment, org=org, student_label=str(student))
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="receipt_payment_{payment.pk}.pdf"'
    return response


@role_required(Role.STUDENT)
def invoice_print(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term")
        .prefetch_related("lines", "payments"),
        pk=pk,
        student=student,
    )
    amounts = invoice_amounts(invoice)
    org = get_or_create_organization()
    return render(
        request,
        "portals/student/finance/invoice_print.html",
        {
            "student": student,
            "invoice": invoice,
            "org": org,
            "total_amount": amounts.total_amount,
            "subtotal_lines": amounts.subtotal_lines,
            "total_paid": amounts.total_paid,
            "balance": amounts.balance,
        },
    )
