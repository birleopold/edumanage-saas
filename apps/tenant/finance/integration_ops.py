from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.portals.permissions import admin_portal_required

from .integration_ops_forms import IntegrationApiKeyCreateForm, IntegrationScopeForm, WebhookEndpointForm
from .models import (
    BiometricAttendanceEvent,
    BiometricDevice,
    InboundWebhookEvent,
    IntegrationApiKey,
    IntegrationApiKeyScope,
    IntegrationEventLog,
    IntegrationProviderConfig,
    IntegrationScope,
    MeetingSessionLink,
    SSOLoginProvider,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookRetryQueueItem,
)


TABS = [
    ("providers", "Providers"),
    ("api-keys", "API Keys"),
    ("scopes", "Scopes"),
    ("webhooks", "Webhooks"),
    ("deliveries", "Webhook Deliveries"),
    ("retry-queue", "Retry Queue"),
    ("inbound-events", "Inbound Events"),
    ("sso", "SSO Providers"),
    ("biometric-devices", "Biometric Devices"),
    ("biometric-events", "Biometric Events"),
    ("meeting-links", "Meeting Links"),
    ("event-logs", "Event Logs"),
]


def _paginate(request, qs, per_page=30):
    return Paginator(qs, per_page).get_page(request.GET.get("page") or 1)


def _masked(value, visible=4):
    if not value:
        return "Not set"
    value = str(value)
    if len(value) <= visible:
        return "••••"
    return f"••••••{value[-visible:]}"


def _base_context(request, active_tab):
    return {
        "tabs": TABS,
        "active_tab": active_tab,
        "provider_count": IntegrationProviderConfig.objects.count(),
        "active_provider_count": IntegrationProviderConfig.objects.filter(is_active=True).count(),
        "api_key_count": IntegrationApiKey.objects.count(),
        "active_api_key_count": IntegrationApiKey.objects.filter(is_active=True).count(),
        "webhook_count": WebhookEndpoint.objects.count(),
        "failed_delivery_count": WebhookDelivery.objects.filter(success=False).count(),
        "retry_count": WebhookRetryQueueItem.objects.filter(is_active=True).count(),
        "inbound_error_count": InboundWebhookEvent.objects.filter(signature_valid=False).count(),
    }


def _provider_rows():
    rows = []
    for item in IntegrationProviderConfig.objects.order_by("provider_type", "name"):
        rows.append(
            {
                "item": item,
                "client_secret_masked": _masked(item.client_secret),
                "access_token_masked": _masked(item.access_token),
                "webhook_secret_masked": _masked(item.webhook_secret),
            }
        )
    return rows


def _api_key_rows():
    rows = []
    for item in IntegrationApiKey.objects.prefetch_related("scope_links__scope").order_by("-created_at"):
        rows.append({"item": item, "scopes": [link.scope for link in item.scope_links.all()]})
    return rows


@admin_portal_required
def integrations_center(request, tab="providers"):
    active_tab = tab if tab in dict(TABS) else "providers"
    context = _base_context(request, active_tab)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if active_tab == "providers":
        context.update({"provider_rows": _provider_rows(), "provider_type_counts": IntegrationProviderConfig.objects.values("provider_type").annotate(total=Count("id"))})
    elif active_tab == "api-keys":
        context.update({"api_key_rows": _api_key_rows(), "api_key_form": IntegrationApiKeyCreateForm()})
    elif active_tab == "scopes":
        context.update({"scopes": IntegrationScope.objects.order_by("code"), "scope_form": IntegrationScopeForm()})
    elif active_tab == "webhooks":
        context.update({"webhooks": WebhookEndpoint.objects.order_by("name"), "webhook_form": WebhookEndpointForm()})
    elif active_tab == "deliveries":
        qs = WebhookDelivery.objects.select_related("endpoint").order_by("-created_at")
        if status == "failed":
            qs = qs.filter(success=False)
        elif status == "success":
            qs = qs.filter(success=True)
        context.update({"page_obj": _paginate(request, qs), "status": status})
    elif active_tab == "retry-queue":
        qs = WebhookRetryQueueItem.objects.select_related("endpoint").order_by("-is_active", "next_attempt_at")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        context.update({"page_obj": _paginate(request, qs), "status": status})
    elif active_tab == "inbound-events":
        qs = InboundWebhookEvent.objects.order_by("-created_at")
        if status == "invalid":
            qs = qs.filter(signature_valid=False)
        elif status == "valid":
            qs = qs.filter(signature_valid=True)
        context.update({"page_obj": _paginate(request, qs), "status": status})
    elif active_tab == "sso":
        context.update({"sso_providers": SSOLoginProvider.objects.order_by("provider_type", "name")})
    elif active_tab == "biometric-devices":
        context.update({"devices": BiometricDevice.objects.select_related("campus", "provider").order_by("name")})
    elif active_tab == "biometric-events":
        qs = BiometricAttendanceEvent.objects.select_related("device", "student", "offering").order_by("-event_time")
        if status == "processed":
            qs = qs.filter(processed=True)
        elif status == "failed":
            qs = qs.filter(processed=False)
        context.update({"page_obj": _paginate(request, qs), "status": status})
    elif active_tab == "meeting-links":
        context.update({"meeting_links": MeetingSessionLink.objects.select_related("provider", "offering", "created_by").order_by("-created_at")[:100]})
    elif active_tab == "event-logs":
        qs = IntegrationEventLog.objects.select_related("provider", "api_key").order_by("-created_at")
        if q:
            qs = qs.filter(Q(event_type__icontains=q) | Q(external_reference__icontains=q) | Q(error_message__icontains=q))
        if status:
            qs = qs.filter(status=status)
        context.update({"page_obj": _paginate(request, qs), "q": q, "status": status, "event_status_choices": IntegrationEventLog.STATUS_CHOICES})

    return render(request, "portals/admin/integrations/center.html", context)


@admin_portal_required
@require_POST
def api_key_create(request):
    form = IntegrationApiKeyCreateForm(request.POST)
    if form.is_valid():
        key, raw_key = IntegrationApiKey.create_with_plaintext(form.cleaned_data["name"])
        for scope in form.cleaned_data["scopes"]:
            IntegrationApiKeyScope.objects.create(api_key=key, scope=scope)
        messages.success(request, f"API key created. Copy now: {raw_key}")
    else:
        messages.error(request, "API key could not be created.")
    return redirect(f"{reverse('admin_connectors_tab', args=['api-keys'])}")


@admin_portal_required
@require_POST
def api_key_rotate(request, pk):
    old_key = get_object_or_404(IntegrationApiKey, pk=pk)
    scopes = list(IntegrationScope.objects.filter(api_key_links__api_key=old_key))
    old_key.is_active = False
    old_key.save(update_fields=["is_active"])
    new_key, raw_key = IntegrationApiKey.create_with_plaintext(f"{old_key.name} rotated")
    for scope in scopes:
        IntegrationApiKeyScope.objects.create(api_key=new_key, scope=scope)
    messages.success(request, f"Key rotated. Copy the new key now: {raw_key}")
    return redirect(f"{reverse('admin_connectors_tab', args=['api-keys'])}")


@admin_portal_required
@require_POST
def api_key_toggle(request, pk):
    key = get_object_or_404(IntegrationApiKey, pk=pk)
    key.is_active = not key.is_active
    key.save(update_fields=["is_active"])
    messages.success(request, "API key status updated.")
    return redirect(f"{reverse('admin_connectors_tab', args=['api-keys'])}")


@admin_portal_required
@require_POST
def scope_create(request):
    form = IntegrationScopeForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Scope saved.")
    else:
        messages.error(request, "Scope could not be saved.")
    return redirect(f"{reverse('admin_connectors_tab', args=['scopes'])}")


@admin_portal_required
@require_POST
def webhook_create(request):
    form = WebhookEndpointForm(request.POST)
    if form.is_valid():
        endpoint = form.save(commit=False)
        if not endpoint.secret:
            endpoint.secret = IntegrationApiKey.hash_key(f"{endpoint.name}:{timezone.now().isoformat()}")[:32]
        endpoint.save()
        messages.success(request, "Webhook endpoint saved with a generated secret.")
    else:
        messages.error(request, "Webhook endpoint could not be saved.")
    return redirect(f"{reverse('admin_connectors_tab', args=['webhooks'])}")


@admin_portal_required
@require_POST
def webhook_test(request, pk):
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk)
    payload = {"test": True, "endpoint_id": endpoint.pk, "sent_at": timezone.now().isoformat()}
    WebhookRetryQueueItem.objects.create(endpoint=endpoint, event_type=endpoint.event_type, payload=payload, next_attempt_at=timezone.now())
    IntegrationEventLog.objects.create(event_type="webhook.test.queued", direction=IntegrationEventLog.OUTBOUND, status=IntegrationEventLog.PENDING, request_payload=payload, external_reference=str(endpoint.pk))
    messages.success(request, "Test webhook queued for delivery by the webhook worker.")
    return redirect(f"{reverse('admin_connectors_tab', args=['webhooks'])}")


@admin_portal_required
@require_POST
def retry_queue_now(request, pk):
    item = get_object_or_404(WebhookRetryQueueItem, pk=pk)
    item.next_attempt_at = timezone.now()
    item.is_active = True
    item.save(update_fields=["next_attempt_at", "is_active", "updated_at"])
    IntegrationEventLog.objects.create(event_type="webhook.retry.requested", direction=IntegrationEventLog.OUTBOUND, status=IntegrationEventLog.PENDING, request_payload={"retry_item_id": item.pk}, external_reference=str(item.pk))
    messages.success(request, "Retry item moved to immediate queue.")
    return redirect(f"{reverse('admin_connectors_tab', args=['retry-queue'])}")


@admin_portal_required
@require_POST
def provider_test(request, pk):
    provider = get_object_or_404(IntegrationProviderConfig, pk=pk)
    provider.last_tested_at = timezone.now()
    provider.last_test_status = "QUEUED"
    provider.last_error = ""
    provider.save(update_fields=["last_tested_at", "last_test_status", "last_error"])
    IntegrationEventLog.objects.create(provider=provider, event_type="provider.test.queued", direction=IntegrationEventLog.OUTBOUND, status=IntegrationEventLog.PENDING, request_payload={"provider_id": provider.pk}, external_reference=str(provider.pk))
    messages.success(request, "Provider test queued/logged.")
    return redirect(f"{reverse('admin_connectors_tab', args=['providers'])}")
