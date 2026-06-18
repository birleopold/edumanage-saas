from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django import forms

from apps.tenant.finance.models import CommunicationTemplate, OutboundMessageLog
from apps.tenant.portals.permissions import admin_portal_required


class CommunicationTemplateForm(forms.ModelForm):
    class Meta:
        model = CommunicationTemplate
        fields = ["sort_order", "code", "name", "message_type", "channel_hint", "body", "is_active"]
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}


@admin_portal_required
def delivery_dashboard(request):
    logs = OutboundMessageLog.objects.order_by("-created_at")[:200]
    summary = {
        "sent": OutboundMessageLog.objects.filter(status=OutboundMessageLog.SENT).count(),
        "failed": OutboundMessageLog.objects.filter(status=OutboundMessageLog.FAILED).count(),
        "dry_run": OutboundMessageLog.objects.filter(status=OutboundMessageLog.DRY_RUN).count(),
        "no_phone": OutboundMessageLog.objects.filter(status=OutboundMessageLog.NO_PHONE).count(),
        "delivered": OutboundMessageLog.objects.filter(provider_delivery_status__iexact="delivered").count(),
        "read": OutboundMessageLog.objects.filter(provider_delivery_status__iexact="read").count(),
    }
    return render(request, "portals/messaging/delivery_dashboard.html", {"summary": summary, "logs": logs})


@admin_portal_required
def template_list(request):
    items = CommunicationTemplate.objects.order_by("sort_order", "code")
    return render(request, "portals/messaging/templates_list.html", {"items": items})


@admin_portal_required
def template_edit(request, pk=None):
    obj = get_object_or_404(CommunicationTemplate, pk=pk) if pk else None
    form = CommunicationTemplateForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Message template saved.")
        return redirect("msg_copy")
    return render(request, "portals/messaging/template_form.html", {"form": form, "obj": obj})
