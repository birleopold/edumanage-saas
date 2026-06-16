from django.contrib import messages
from django.shortcuts import redirect, render

from apps.tenant.portals.permissions import admin_portal_required

from . import services as finance_services
from .models import OutboundMessageLog, WebhookRetryQueueItem


@admin_portal_required
def communication_operations(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "send_test_message":
            phone = (request.POST.get("phone") or "").strip()
            channel = (request.POST.get("channel") or "").strip().upper() or None
            body = (request.POST.get("message") or "").strip()
            dry_run = request.POST.get("dry_run") == "1"
            if not phone:
                messages.error(request, "Enter a phone number before sending a test message.")
            else:
                result = finance_services.send_test_message(
                    phone=phone,
                    message=body,
                    channel=channel,
                    dry_run=dry_run,
                )
                status = result.get("status")
                if status == "sent":
                    messages.success(request, f"Test message sent to {phone}.")
                elif status == "dry_run":
                    messages.info(request, f"Dry-run test message logged for {phone}.")
                else:
                    messages.error(request, f"Test message failed for {phone}: {result.get('error', 'check logs')}")
            return redirect("admin_finance_communication_operations")

        if action == "retry_failed_messages":
            dry_run = request.POST.get("dry_run") == "1"
            message_type = (request.POST.get("message_type") or "").strip().upper()
            limit_raw = request.POST.get("limit") or 50
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = 50
            summary = finance_services.retry_outbound_message_logs(
                limit=limit,
                dry_run=dry_run,
                only_failed=True,
                message_type=message_type,
            )
            messages.success(
                request,
                "Retry complete: processed={processed}, sent={sent}, failed={failed}, skipped={skipped}, dry_run={dry}.".format(
                    processed=summary.get("processed", 0),
                    sent=summary.get("sent", 0),
                    failed=summary.get("failed", 0),
                    skipped=summary.get("skipped", 0),
                    dry=summary.get("dry_run_count", 0),
                ),
            )
            return redirect("admin_finance_communication_operations")

        if action == "process_webhook_retries":
            dry_run = request.POST.get("dry_run") == "1"
            limit_raw = request.POST.get("limit") or 50
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = 50
            summary = finance_services.process_webhook_retry_queue(limit=limit, dry_run=dry_run)
            messages.success(
                request,
                "Webhook retry queue: processed={processed}, sent={sent}, failed={failed}, deactivated={deactivated}.".format(
                    processed=summary.get("processed", 0),
                    sent=summary.get("sent", 0),
                    failed=summary.get("failed", 0),
                    deactivated=summary.get("deactivated", 0),
                ),
            )
            return redirect("admin_finance_communication_operations")

        messages.error(request, "Invalid communication action.")
        return redirect("admin_finance_communication_operations")

    readiness = finance_services.messaging_readiness_snapshot(sample_limit=100)
    recent_failed = OutboundMessageLog.objects.filter(status=OutboundMessageLog.FAILED).order_by("-created_at")[:10]
    recent_logs = OutboundMessageLog.objects.order_by("-created_at")[:15]
    webhook_queue_count = WebhookRetryQueueItem.objects.filter(is_active=True).count()

    return render(
        request,
        "portals/admin/finance/communication_operations.html",
        {
            "readiness": readiness,
            "recent_failed": recent_failed,
            "recent_logs": recent_logs,
            "webhook_queue_count": webhook_queue_count,
            "message_type_options": [
                "",
                OutboundMessageLog.FEE_REMINDER,
                OutboundMessageLog.PAYMENT_RECEIPT,
                OutboundMessageLog.ABSENCE_ALERT,
                OutboundMessageLog.URGENT_ANNOUNCEMENT,
            ],
            "channel_options": [OutboundMessageLog.SMS, OutboundMessageLog.WHATSAPP],
        },
    )
