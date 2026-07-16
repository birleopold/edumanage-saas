from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .models import Payment


def _payment_queryset_for(user):
    qs = Payment.objects.select_related(
        "invoice",
        "invoice__student",
        "invoice__student__campus",
        "invoice__academic_year",
        "invoice__academic_term",
    )
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(invoice__student__campus=scoped)
    return qs


@admin_portal_required
def payment_detail(request, pk: int):
    payment = get_object_or_404(_payment_queryset_for(request.user), pk=pk)
    return render(request, "portals/admin/finance/transaction_detail.html", {"payment": payment, "invoice": payment.invoice})
