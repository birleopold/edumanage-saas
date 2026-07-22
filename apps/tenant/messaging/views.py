from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.tenant.portals.permissions import admin_portal_required, roles_required
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role

from .forms import BulkMessageForm, ConversationForm, FINANCE_TOPIC, MessageReplyForm
from .models import Conversation, Message
from .services import send_bulk_message


MESSAGING_ROLES = (
    Role.ADMIN,
    Role.CAMPUS_ADMIN,
    Role.PRINCIPAL,
    Role.TEACHER,
    Role.PARENT,
    Role.STUDENT,
)


def _my_conversations(user):
    return (
        Conversation.objects.filter(participants=user, is_archived=False)
        .prefetch_related("participants", "messages")
        .order_by("-updated_at")
    )


def _messaging_context(request, **extra):
    role_codes = set(request.user.roles.values_list("code", flat=True))
    context = {
        "base_template": base_template_for(request.user),
        "can_bulk_message": bool(
            request.user.is_superuser
            or role_codes.intersection({Role.ADMIN, Role.CAMPUS_ADMIN})
        ),
    }
    context.update(extra)
    return context


@roles_required(*MESSAGING_ROLES)
def inbox(request):
    queryset = _my_conversations(request.user)
    page_obj = Paginator(queryset, 25).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/messaging/inbox.html",
        _messaging_context(
            request,
            conversations=page_obj.object_list,
            page_obj=page_obj,
            box="Inbox",
        ),
    )


@roles_required(*MESSAGING_ROLES)
def outbox(request):
    queryset = (
        Conversation.objects.filter(messages__sender=request.user)
        .distinct()
        .prefetch_related("participants", "messages")
        .order_by("-updated_at")
    )
    page_obj = Paginator(queryset, 25).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/messaging/inbox.html",
        _messaging_context(
            request,
            conversations=page_obj.object_list,
            page_obj=page_obj,
            box="Outbox",
        ),
    )


@roles_required(*MESSAGING_ROLES)
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related("messages", "participants"),
        pk=pk,
        participants=request.user,
    )
    conversation.mark_as_read(request.user)
    form = MessageReplyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.conversation = conversation
        message.sender = request.user
        message.save()
        message.read_by.add(request.user)
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["updated_at"])
        return redirect("messaging_conversation_detail", pk=conversation.pk)
    return render(
        request,
        "portals/messaging/conversation_detail.html",
        _messaging_context(
            request,
            conversation=conversation,
            messages_list=conversation.messages.order_by("sent_at"),
            form=form,
        ),
    )


@roles_required(*MESSAGING_ROLES)
def conversation_new(request):
    role_code = (request.GET.get("role") or "").strip().upper()
    topic = (request.GET.get("topic") or "").strip().lower()
    topic = FINANCE_TOPIC if topic == FINANCE_TOPIC else ""

    initial = {}
    title = "New Message"
    compose_description = (
        "Start a secure conversation with an authorised school contact."
    )
    if topic == FINANCE_TOPIC:
        invoice_reference = (request.GET.get("invoice") or "").strip()[:80]
        title = "Ask Finance Office"
        compose_description = (
            "Send a private invoice or payment question to an authorised finance-office "
            "or school administration contact."
        )
        initial["subject"] = (
            f"Invoice question: {invoice_reference}"
            if invoice_reference
            else "Invoice or payment question"
        )

    form = ConversationForm(
        request.POST or None,
        request.FILES or None,
        role_code=role_code,
        topic=topic,
        current_user=request.user,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        recipient = form.cleaned_data["recipient"]
        conversation = Conversation.objects.create(
            subject=form.cleaned_data["subject"],
            created_by=request.user,
        )
        conversation.participants.add(request.user, recipient)
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=form.cleaned_data["content"],
            attachment=form.cleaned_data.get("attachment"),
        )
        message.read_by.add(request.user)
        messages.success(request, "Message sent.")
        return redirect("messaging_conversation_detail", pk=conversation.pk)

    return render(
        request,
        "portals/messaging/conversation_form.html",
        _messaging_context(
            request,
            form=form,
            title=title,
            compose_description=compose_description,
            topic=topic,
            no_recipients=not form.fields["recipient"].queryset.exists(),
        ),
    )


@roles_required(Role.PARENT, Role.TEACHER)
def parent_teacher_chat(request):
    role_code = Role.TEACHER if request.user.has_role(Role.PARENT) else Role.PARENT
    target = reverse("messaging_conversation_new")
    return redirect(f"{target}?{urlencode({'role': role_code})}")


@admin_portal_required
def bulk_message(request):
    form = BulkMessageForm(request.POST or None)
    result = None
    if request.method == "POST" and form.is_valid():
        result = send_bulk_message(sender=request.user, form_data=form.cleaned_data)
        messages.success(
            request,
            "Group message processed. "
            f"Sent: {result.get('sent', 0)}, "
            f"Failed: {result.get('failed', 0)}, "
            f"Skipped: {result.get('skipped', 0)}.",
        )
    return render(
        request,
        "portals/messaging/bulk_message.html",
        {"form": form, "result": result},
    )
