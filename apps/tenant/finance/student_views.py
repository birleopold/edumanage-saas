from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Invoice


@role_required(Role.STUDENT)
def invoice_list(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    invoices = list(
        Invoice.objects.filter(student=student).prefetch_related("lines", "payments")
    )

    for inv in invoices:
        inv.total_amount = inv.total_amount()
        inv.total_paid = inv.total_paid()
        inv.balance = inv.balance()

    return render(
        request,
        "portals/student/finance/invoices_list.html",
        {"student": student, "invoices": invoices},
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

    return render(
        request,
        "portals/student/finance/invoice_detail.html",
        {
            "student": student,
            "invoice": invoice,
            "total_amount": invoice.total_amount(),
            "total_paid": invoice.total_paid(),
            "balance": invoice.balance(),
        },
    )
