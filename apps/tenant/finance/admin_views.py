import csv
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.orgsettings.utils import log_action
from apps.tenant.portals.campus_permissions import get_user_campus_scope, user_can_access_campus
from apps.tenant.portals.permissions import admin_portal_required

from .forms import CarryForwardForm, FeeItemForm, InvoiceForm, InvoiceLineForm, PaymentForm
from .models import FeeItem, Invoice, InvoiceLine, OutboundMessageLog, Payment
from .pdf_receipt import generate_payment_receipt_pdf
from . import services as finance_services


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


def _invoice_list_base_queryset(request):
    """Campus + search filters shared by list, export, and overdue toggle."""
    q = (request.GET.get("q") or "").strip()
    campus_id = _selected_campus_id(request)

    qs = Invoice.objects.select_related(
        "student",
        "student__campus",
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

    return qs


def _invoice_list_filtered_queryset(request):
    """Base queryset plus optional overdue filter (annotates when overdue)."""
    qs = _invoice_list_base_queryset(request)
    if request.GET.get("overdue") == "1":
        qs = finance_services.filter_invoices_overdue(qs)
    return qs


@admin_portal_required
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


@admin_portal_required
def fee_item_create(request):
    if request.method == "POST":
        form = FeeItemForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_fee_items_list")
    else:
        form = FeeItemForm()
    return render(request, "portals/admin/finance/fee_item_form.html", {"form": form, "mode": "create"})


@admin_portal_required
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


@admin_portal_required
def payment_receipt_pdf(request, pk: int):
    payment = get_object_or_404(
        Payment.objects.select_related("invoice", "invoice__student", "invoice__student__campus"),
        pk=pk,
    )
    st = payment.invoice.student
    campus = getattr(st, "campus", None)
    scoped = get_user_campus_scope(request.user)
    if scoped is not None:
        if campus is None or not user_can_access_campus(request.user, campus):
            return HttpResponseForbidden("You cannot access this receipt.")
    org = get_or_create_organization()
    buf = generate_payment_receipt_pdf(payment=payment, org=org, student_label=str(st))
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="receipt_payment_{payment.pk}.pdf"'
    return response


@admin_portal_required
def invoice_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)
    overdue_only = request.GET.get("overdue") == "1"

    qs = _invoice_list_filtered_queryset(request)

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
            "overdue_only": overdue_only,
        },
    )


@admin_portal_required
def invoice_export_csv(request):
    """Export invoices matching current list filters (no pagination)."""
    qs = _invoice_list_filtered_queryset(request).order_by("-created_at", "pk")
    if request.GET.get("overdue") != "1":
        qs = finance_services.annotate_invoice_calc_balance(qs)

    filename = f"invoices_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(
        [
            "invoice_id",
            "reference",
            "status",
            "student_id",
            "student_name",
            "campus",
            "academic_year",
            "term",
            "due_date",
            "opening_balance",
            "line_items_total",
            "total_due",
            "total_paid",
            "balance",
        ]
    )
    for inv in qs.iterator():
        ob = inv.opening_balance if inv.opening_balance is not None else 0
        lines_total = inv._lines_sum
        paid = inv._paid_sum
        total = ob + lines_total
        bal = inv._calc_balance
        writer.writerow(
            [
                inv.pk,
                inv.reference or "",
                inv.status,
                inv.student.student_id or "",
                str(inv.student),
                inv.student.campus.name if getattr(inv.student, "campus_id", None) else "",
                str(inv.academic_year) if inv.academic_year_id else "",
                str(inv.academic_term) if inv.academic_term_id else "",
                inv.due_date.isoformat() if inv.due_date else "",
                str(ob),
                str(lines_total),
                str(total),
                str(paid),
                str(bal),
            ]
        )
    return response


@admin_portal_required
def invoice_clone(request, pk: int):
    """
    Copy fee line items onto a new invoice for the same student in another year/term.
    """
    source = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term").prefetch_related(
            "lines"
        ),
        pk=pk,
    )

    if request.method == "POST":
        form = CarryForwardForm(request.POST)
        if form.is_valid():
            try:
                new_inv = finance_services.clone_invoice_to_new_period(
                    source,
                    target_year=form.cleaned_data["target_year"],
                    target_term=form.cleaned_data["target_term"],
                )
            except ValueError as e:
                messages.error(request, str(e))
            else:
                log_action(
                    source,
                    "INVOICE_CLONE_OUT",
                    description=f"Cloned line items to invoice #{new_inv.pk}.",
                    user=request.user,
                    metadata={
                        "new_invoice_id": new_inv.pk,
                        "target_year_id": form.cleaned_data["target_year"].pk,
                        "target_term_id": form.cleaned_data["target_term"].pk,
                    },
                )
                log_action(
                    new_inv,
                    "INVOICE_CLONE_IN",
                    description=f"Created from invoice #{source.pk} (line items copied).",
                    user=request.user,
                    metadata={"source_invoice_id": source.pk},
                )
                messages.success(
                    request,
                    f"New invoice #{new_inv.pk} created in the selected period with copied fee lines.",
                )
                return redirect("admin_invoices_detail", pk=new_inv.pk)
    else:
        form = CarryForwardForm()

    return render(
        request,
        "portals/admin/finance/invoice_clone.html",
        {"source": source, "form": form},
    )


@admin_portal_required
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


@admin_portal_required
def invoice_carry_forward(request, pk: int):
    """
    Move remaining balance onto another academic period (same student).
    """
    source = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term"),
        pk=pk,
    )
    balance = source.balance()
    if balance <= 0:
        messages.info(request, "This invoice has no positive balance to carry forward.")
        return redirect("admin_invoices_detail", pk=source.pk)

    if request.method == "POST":
        form = CarryForwardForm(request.POST)
        if form.is_valid():
            try:
                target_inv, action = finance_services.carry_balance_to_target_term(
                    source,
                    target_year=form.cleaned_data["target_year"],
                    target_term=form.cleaned_data["target_term"],
                )
            except ValueError as e:
                messages.error(request, str(e))
            else:
                bal_amt = balance
                log_action(
                    source,
                    "CARRY_FORWARD_OUT",
                    description=f"Carried balance {bal_amt} to invoice #{target_inv.pk} ({action}).",
                    user=request.user,
                    metadata={
                        "target_invoice_id": target_inv.pk,
                        "action": action,
                        "target_year_id": form.cleaned_data["target_year"].pk,
                        "target_term_id": form.cleaned_data["target_term"].pk,
                    },
                )
                log_action(
                    target_inv,
                    "CARRY_FORWARD_IN",
                    description=f"Received balance {bal_amt} from invoice #{source.pk}.",
                    user=request.user,
                    metadata={"source_invoice_id": source.pk},
                )
                messages.success(
                    request,
                    f"Balance carried forward ({action}). Target invoice #{target_inv.pk}.",
                )
                return redirect("admin_invoices_detail", pk=target_inv.pk)
    else:
        form = CarryForwardForm()

    return render(
        request,
        "portals/admin/finance/invoice_carry_forward.html",
        {
            "source": source,
            "balance": balance,
            "form": form,
        },
    )


@admin_portal_required
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


@admin_portal_required
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
                if bool(getattr(settings, "FEE_RECEIPT_AUTO_SEND_ON_PAYMENT", False)):
                    org = get_or_create_organization()
                    results = finance_services.send_payment_receipt_for_payment(
                        payment,
                        currency_code=getattr(org, "default_currency", None) or "UGX",
                        school_name=org.name,
                    )
                    parts = [f"{r.get('phone') or '?'}: {r.get('status')}" for r in results]
                    messages.info(request, "Payment receipt dispatch: " + "; ".join(parts))
                    log_action(
                        invoice,
                        "PAYMENT_RECEIPT_MESSAGE",
                        description=f"Payment receipt message sent for payment #{payment.pk}.",
                        user=request.user,
                        metadata={"payment_id": payment.pk, "results": results},
                    )
                return redirect("admin_invoices_detail", pk=invoice.pk)
        elif action == "send_payment_receipt":
            payment_id = request.POST.get("payment_id")
            payment = get_object_or_404(Payment, pk=payment_id, invoice=invoice)
            org = get_or_create_organization()
            results = finance_services.send_payment_receipt_for_payment(
                payment,
                currency_code=getattr(org, "default_currency", None) or "UGX",
                school_name=org.name,
            )
            if results and results[0].get("status") == "no_phone":
                messages.warning(
                    request,
                    "No parent phone numbers on file for this student. Add phones on parent profiles.",
                )
            else:
                parts = [f"{r.get('phone') or '?'}: {r.get('status')}" for r in results]
                messages.success(request, "Payment receipt dispatch: " + "; ".join(parts))
            log_action(
                invoice,
                "PAYMENT_RECEIPT_MESSAGE",
                description=f"Payment receipt message sent for payment #{payment.pk}.",
                user=request.user,
                metadata={"payment_id": payment.pk, "results": results},
            )
            return redirect("admin_invoices_detail", pk=invoice.pk)
        elif action == "send_fee_reminder":
            org = get_or_create_organization()
            results = finance_services.send_fee_reminder_for_invoice(
                invoice,
                currency_code=getattr(org, "default_currency", None) or "UGX",
                school_name=org.name,
            )
            if results and results[0].get("status") == "no_phone":
                messages.warning(
                    request,
                    "No parent phone numbers on file for this student. Add phones on parent profiles.",
                )
            else:
                parts = [f"{r.get('phone') or '?'}: {r.get('status')}" for r in results]
                messages.success(request, "Fee reminder dispatch: " + "; ".join(parts))
            log_action(
                invoice,
                "FEE_REMINDER_SMS",
                description="Fee reminder sent to parent phone(s).",
                user=request.user,
                metadata={"results": results},
            )
            return redirect("admin_invoices_detail", pk=invoice.pk)
        else:
            messages.error(request, "Invalid action.")

    total_amount = invoice.total_amount()
    total_paid = invoice.total_paid()
    balance = invoice.balance()
    subtotal_lines = invoice.subtotal_lines()

    return render(
        request,
        "portals/admin/finance/invoice_detail.html",
        {
            "invoice": invoice,
            "line_form": line_form,
            "payment_form": payment_form,
            "total_amount": total_amount,
            "subtotal_lines": subtotal_lines,
            "total_paid": total_paid,
            "balance": balance,
        },
    )


@admin_portal_required
def invoice_print(request, pk: int):
    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "academic_year", "academic_term", "student__campus")
        .prefetch_related("lines", "payments"),
        pk=pk,
    )
    org = get_or_create_organization()
    return render(
        request,
        "portals/admin/finance/invoice_print.html",
        {
            "invoice": invoice,
            "org": org,
            "total_amount": invoice.total_amount(),
            "subtotal_lines": invoice.subtotal_lines(),
            "total_paid": invoice.total_paid(),
            "balance": invoice.balance(),
        },
    )


@admin_portal_required
def invoice_line_remove(request, pk: int, line_id: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    line = get_object_or_404(InvoiceLine, pk=line_id, invoice=invoice)
    if request.method == "POST":
        line.delete()
    return redirect("admin_invoices_detail", pk=invoice.pk)


@admin_portal_required
def invoice_payment_remove(request, pk: int, payment_id: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    payment = get_object_or_404(Payment, pk=payment_id, invoice=invoice)
    if request.method == "POST":
        payment.delete()
    return redirect("admin_invoices_detail", pk=invoice.pk)


@admin_portal_required
def message_logs_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request, default=30, max_value=200)
    page_number = request.GET.get("page") or 1
    status = (request.GET.get("status") or OutboundMessageLog.FAILED).strip().upper()
    channel = (request.GET.get("channel") or "").strip().upper()
    message_type = (request.GET.get("message_type") or "").strip().upper()
    campus_id = _selected_campus_id(request)
    campuses = _campus_queryset()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "retry_log":
            log_id = request.POST.get("log_id")
            dry_run = request.POST.get("dry_run") == "1"
            log = get_object_or_404(OutboundMessageLog.objects.select_related("invoice"), pk=log_id)
            if campus_id and log.invoice_id and getattr(log.invoice.student, "campus_id", None) != campus_id:
                return HttpResponseForbidden("You cannot retry logs outside selected campus scope.")
            result = finance_services.retry_outbound_message_log(log, dry_run=dry_run)
            if result.get("status") == "sent":
                messages.success(request, f"Retry succeeded for log #{log.pk}.")
            elif result.get("status") == "dry_run":
                messages.info(request, f"Dry-run retry recorded for log #{log.pk}.")
            elif result.get("status") == "skipped":
                messages.warning(request, f"Retry skipped for log #{log.pk}: {result.get('reason')}")
            else:
                messages.error(request, f"Retry failed for log #{log.pk}.")
            next_url = (request.POST.get("next") or "").strip()
            if next_url:
                return redirect(next_url)
            return redirect("admin_finance_message_logs")
        messages.error(request, "Invalid action.")
        return redirect("admin_finance_message_logs")

    logs_qs = OutboundMessageLog.objects.select_related("invoice", "invoice__student", "payment").order_by(
        "-created_at"
    )
    if status and status != "ALL":
        logs_qs = logs_qs.filter(status=status)
    if channel:
        logs_qs = logs_qs.filter(channel=channel)
    if message_type:
        logs_qs = logs_qs.filter(message_type=message_type)
    if campus_id:
        logs_qs = logs_qs.filter(invoice__student__campus_id=campus_id)
    if q:
        logs_qs = logs_qs.filter(
            Q(phone_raw__icontains=q)
            | Q(phone_normalized__icontains=q)
            | Q(error_message__icontains=q)
            | Q(message__icontains=q)
            | Q(provider_message_id__icontains=q)
            | Q(invoice__reference__icontains=q)
            | Q(invoice__student__first_name__icontains=q)
            | Q(invoice__student__last_name__icontains=q)
        )

    paginator = Paginator(logs_qs, per_page)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "portals/admin/finance/message_logs_list.html",
        {
            "logs": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "status": status,
            "channel": channel,
            "message_type": message_type,
            "campuses": campuses,
            "selected_campus_id": campus_id,
            "status_options": ["ALL", "FAILED", "SENT", "DRY_RUN", "NO_PHONE"],
            "channel_options": ["SMS", "WHATSAPP"],
            "message_type_options": [
                "FEE_REMINDER",
                "PAYMENT_RECEIPT",
                "ABSENCE_ALERT",
                "URGENT_ANNOUNCEMENT",
            ],
        },
    )


@admin_portal_required
def messaging_report(request):
    today = timezone.localdate()
    date_from = request.GET.get("date_from") or (today - timedelta(days=7)).isoformat()
    date_to = request.GET.get("date_to") or today.isoformat()
    q = (request.GET.get("q") or "").strip()

    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)

    logs_qs = OutboundMessageLog.objects.select_related("invoice", "invoice__student").all()
    if date_from:
        logs_qs = logs_qs.filter(created_at__date__gte=date_from)
    if date_to:
        logs_qs = logs_qs.filter(created_at__date__lte=date_to)
    if campus_id:
        logs_qs = logs_qs.filter(invoice__student__campus_id=campus_id)
    if q:
        logs_qs = logs_qs.filter(
            Q(phone_raw__icontains=q)
            | Q(invoice__reference__icontains=q)
            | Q(error_message__icontains=q)
        )

    grouped = (
        logs_qs.values("message_type", "status")
        .annotate(total=Count("id"))
        .order_by("message_type", "status")
    )
    recent_logs = logs_qs.order_by("-created_at")[:30]

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "send_absence_alerts_by_date":
            target_date = request.POST.get("target_date") or today.isoformat()
            include_late = request.POST.get("include_late") == "1"
            dry_run = request.POST.get("dry_run") == "1"
            org = get_or_create_organization()
            summary = finance_services.send_absence_alerts_for_date(
                target_date,
                campus_id=campus_id,
                include_late=include_late,
                school_name=org.name,
                dry_run=dry_run,
            )
            messages.success(
                request,
                "Absence campaign ({date}): sent={sent}, failed={failed}, no_phone={no_phone}, dry_run={dry}".format(
                    date=target_date,
                    sent=summary["sent"],
                    failed=summary["failed"],
                    no_phone=summary["no_phone"],
                    dry=summary["dry_run_count"],
                ),
            )
            return redirect("admin_finance_messaging_report")

    return render(
        request,
        "portals/admin/finance/messaging_report.html",
        {
            "grouped": grouped,
            "recent_logs": recent_logs,
            "date_from": date_from,
            "date_to": date_to,
            "q": q,
            "campuses": campuses,
            "selected_campus_id": campus_id,
            "today": today.isoformat(),
        },
    )
