from django.contrib import messages
from django.shortcuts import redirect, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .forms import BulkInvoiceForm
from .invoicing import bulk_create_invoices, collection_summary
from .models import Invoice


@admin_portal_required
def invoice_bulk_create(request):
    campus_scope = get_user_campus_scope(request.user)

    if request.method == "POST":
        form = BulkInvoiceForm(request.POST, campus_scope=campus_scope)
        if form.is_valid():
            students = form.matching_students()
            student_count = students.count()
            if student_count == 0:
                messages.error(request, "No active students matched your billing filters.")
            else:
                result = bulk_create_invoices(
                    students=students,
                    academic_year=form.cleaned_data["academic_year"],
                    academic_term=form.cleaned_data["academic_term"],
                    fee_items=form.cleaned_data["fee_items"],
                    due_date=form.cleaned_data.get("due_date"),
                    opening_balance=form.cleaned_data.get("opening_balance") or 0,
                    reference_prefix=form.cleaned_data.get("reference_prefix") or "INV",
                    skip_existing=form.cleaned_data.get("skip_existing"),
                )
                messages.success(
                    request,
                    "Bulk billing complete: {created} invoice(s) created, {skipped} skipped, {failed} failed.".format(
                        created=result["created_count"],
                        skipped=result["skipped_existing_count"],
                        failed=result["failed_count"],
                    ),
                )
                if result["created_count"] == 1:
                    return redirect("admin_invoices_detail", pk=result["created"][0].pk)
                return redirect("admin_invoices_list")
    else:
        form = BulkInvoiceForm(campus_scope=campus_scope)

    current_summary = collection_summary(
        Invoice.objects.select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments")
    )
    return render(
        request,
        "portals/admin/finance/invoice_bulk_create.html",
        {
            "form": form,
            "current_summary": current_summary,
        },
    )
