from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.orgsettings.services import (
    campus_queryset,
    get_or_create_organization,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import Invoice, Payment
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

    links_qs = ParentStudentLink.objects.filter(parent=parent).select_related("student", "student__campus")
    if campus_id:
        links_qs = links_qs.filter(student__campus_id=campus_id)

    invoices = list(
        Invoice.objects.filter(student_id__in=student_ids)
        .select_related("student", "academic_year", "academic_term")
        .prefetch_related("lines", "payments")
        .order_by("student__last_name", "student__first_name", "-created_at")
    )

    for inv in invoices:
        inv.total_amount = inv.total_amount()
        inv.total_paid = inv.total_paid()
        inv.balance = inv.balance()

    return render(
        request,
        "portals/parent/finance/invoices_list.html",
        {"parent": parent, "invoices": invoices, "campuses": campuses, "selected_campus_id": campus_id},
    )


@role_required(Role.PARENT)
def invoice_detail(request, pk: int):
    parent, student_ids = _parent_student_ids(request)
    if parent is None:
        return HttpResponseForbidden("No parent profile linked to this account.")
    if not student_ids:
        raise Http404("No linked students for this filter.")

    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term")
        .prefetch_related("lines", "payments"),
        pk=pk,
        student_id__in=student_ids,
    )

    return render(
        request,
        "portals/parent/finance/invoice_detail.html",
        {
            "parent": parent,
            "invoice": invoice,
            "total_amount": invoice.total_amount(),
            "subtotal_lines": invoice.subtotal_lines(),
            "total_paid": invoice.total_paid(),
            "balance": invoice.balance(),
        },
    )


@role_required(Role.PARENT)
def payment_receipt_pdf(request, pk: int, payment_id: int):
    parent, student_ids = _parent_student_ids(request)
    if parent is None:
        return HttpResponseForbidden("No parent profile linked to this account.")
    if not student_ids:
        raise Http404("No linked students for this filter.")

    payment = get_object_or_404(
        Payment.objects.select_related("invoice", "invoice__student"),
        pk=payment_id,
        invoice_id=pk,
        invoice__student_id__in=student_ids,
    )
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

    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term")
        .prefetch_related("lines", "payments"),
        pk=pk,
        student_id__in=student_ids,
    )
    org = get_or_create_organization()
    return render(
        request,
        "portals/parent/finance/invoice_print.html",
        {
            "parent": parent,
            "invoice": invoice,
            "org": org,
            "total_amount": invoice.total_amount(),
            "subtotal_lines": invoice.subtotal_lines(),
            "total_paid": invoice.total_paid(),
            "balance": invoice.balance(),
        },
    )
