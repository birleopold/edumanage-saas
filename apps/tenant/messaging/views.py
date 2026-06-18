from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.permissions import admin_portal_required, roles_required
from apps.tenant.users.models import Role

from .forms import BulkMessageForm, ConversationForm, MessageReplyForm
from .models import Conversation, Message
from .services import send_bulk_message


def _my_conversations(user):
    return Conversation.objects.filter(participants=user, is_archived=False).prefetch_related("participants", "messages").order_by("-updated_at")


@roles_required(Role.ADMIN, Role.CAMPUS_ADMIN, Role.TEACHER, Role.PARENT, Role.STUDENT)
def inbox(request):
    qs = _my_conversations(request.user)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page") or 1)
    return render(request, "portals/messaging/inbox.html", {"conversations": page_obj.object_list, "page_obj": page_obj, "box": "Inbox"})


@roles_required(Role.ADMIN, Role.CAMPUS_ADMIN, Role.TEACHER, Role.PARENT, Role.STUDENT)
def outbox(request):
    qs = Conversation.objects.filter(messages__sender=request.user).distinct().prefetch_related("participants", "messages").order_by("-updated_at")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page") or 1)
    return render(request, "portals/messaging/inbox.html", {"conversations": page_obj.object_list, "page_obj": page_obj, "box": "Outbox"})


@roles_required(Role.ADMIN, Role.CAMPUS_ADMIN, Role.TEACHER, Role.PARENT, Role.STUDENT)
def conversation_detail(request, pk):
    convo = get_object_or_404(Conversation.objects.prefetch_related("messages", "participants"), pk=pk, participants=request.user)
    convo.mark_as_read(request.user)
    form = MessageReplyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        msg = form.save(commit=False)
        msg.conversation = convo
        msg.sender = request.user
        msg.save()
        msg.read_by.add(request.user)
        convo.updated_at = timezone.now()
        convo.save(update_fields=["updated_at"])
        return redirect("messaging_conversation_detail", pk=convo.pk)
    return render(request, "portals/messaging/conversation_detail.html", {"conversation": convo, "messages_list": convo.messages.order_by("sent_at"), "form": form})


@roles_required(Role.ADMIN, Role.CAMPUS_ADMIN, Role.TEACHER, Role.PARENT, Role.STUDENT)
def conversation_new(request):
    role_code = request.GET.get("role") or ""
    form = ConversationForm(request.POST or None, request.FILES or None, role_code=role_code)
    if request.method == "POST" and form.is_valid():
        recipient = form.cleaned_data["recipient"]
        convo = Conversation.objects.create(subject=form.cleaned_data["subject"], created_by=request.user)
        convo.participants.add(request.user, recipient)
        msg = Message.objects.create(conversation=convo, sender=request.user, content=form.cleaned_data["content"], attachment=form.cleaned_data.get("attachment"))
        msg.read_by.add(request.user)
        messages.success(request, "Message sent.")
        return redirect("messaging_conversation_detail", pk=convo.pk)
    return render(request, "portals/messaging/conversation_form.html", {"form": form, "title": "New Message"})


@roles_required(Role.PARENT, Role.TEACHER)
def parent_teacher_chat(request):
    role_code = Role.TEACHER if request.user.has_role(Role.PARENT) else Role.PARENT
    return redirect(f"/messages/new/?role={role_code}")


@admin_portal_required
def bulk_message(request):
    form = BulkMessageForm(request.POST or None)
    result = None
    if request.method == "POST" and form.is_valid():
        result = send_bulk_message(sender=request.user, form_data=form.cleaned_data)
        messages.success(request, f"Bulk message processed. Sent: {result.get('sent', 0)}, Failed: {result.get('failed', 0)}, Skipped: {result.get('skipped', 0)}.")
    return render(request, "portals/messaging/bulk_message.html", {"form": form, "result": result})
