from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.permissions import admin_portal_required

from .models import Payment


@admin_portal_required
def payment_detail(request, pk: int):
    payment = get_object_or_404(
        Payment.objects.select_related(
            "invoice",
            "invoice__student",
            "invoice__academic_year",
            "invoice__academic_term",
        ),
        pk=pk,
    )
    return render(request, "portals/admin/finance/transaction_detail.html", {"payment": payment, "invoice": payment.invoice})
