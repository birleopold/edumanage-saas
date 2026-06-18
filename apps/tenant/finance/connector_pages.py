from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import admin_portal_required

from .connector_forms import ProviderForm
from .integration_services import provider_readiness_summary
from .models import IntegrationEventLog, IntegrationProviderConfig


@admin_portal_required
def connector_home(request):
    return render(request, "portals/admin/integrations/home.html", {"summary": provider_readiness_summary(), "providers": IntegrationProviderConfig.objects.all(), "events": IntegrationEventLog.objects.order_by("-created_at")[:30]})


@admin_portal_required
def provider_edit(request, pk=None):
    obj = get_object_or_404(IntegrationProviderConfig, pk=pk) if pk else None
    form = ProviderForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Provider saved.")
        return redirect("admin_connectors_home")
    return render(request, "portals/admin/integrations/provider_form.html", {"form": form, "obj": obj})
