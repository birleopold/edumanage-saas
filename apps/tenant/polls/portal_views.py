from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.portals.campus_permissions import enforce_campus_scope, get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.device_portal import base_template_for

from .forms import PollForm, PollOptionForm, PollVoteForm
from .models import Poll, PollVote
from .portal_services import current_vote, polls_for_user, request_key, results_allowed


def _admin_polls(request):
    return enforce_campus_scope(
        Poll.objects.select_related("campus", "created_by"),
        request.user,
    )


def _portal_context(request, **context):
    return {"base_template": base_template_for(request.user), **context}


@admin_portal_required
def admin_poll_list(request):
    polls = (
        _admin_polls(request)
        .prefetch_related("options")
        .annotate(vote_total=Count("votes"))
        .order_by("-created_at")
    )
    return render(request, "portals/admin/polls/list.html", {"polls": polls})


@admin_portal_required
def admin_poll_create(request):
    form = PollForm(
        request.POST or None,
        campus_scope=get_user_campus_scope(request.user),
    )
    if request.method == "POST" and form.is_valid():
        poll = form.save(commit=False)
        poll.created_by = request.user
        poll.save()
        form.save_m2m()
        messages.success(request, "Poll created. Add options before publishing.")
        return redirect("admin_poll_detail", pk=poll.pk)
    return render(request, "portals/admin/polls/form.html", {"form": form, "mode": "create"})


@admin_portal_required
def admin_poll_edit(request, pk):
    poll = get_object_or_404(_admin_polls(request), pk=pk)
    form = PollForm(
        request.POST or None,
        instance=poll,
        campus_scope=get_user_campus_scope(request.user),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Poll updated.")
        return redirect("admin_poll_detail", pk=poll.pk)
    return render(
        request,
        "portals/admin/polls/form.html",
        {"form": form, "poll": poll, "mode": "edit"},
    )


@admin_portal_required
def admin_poll_detail(request, pk):
    poll = get_object_or_404(
        _admin_polls(request).prefetch_related(
            "options",
            "votes",
            "specific_students",
            "specific_teachers",
        ),
        pk=pk,
    )
    return render(
        request,
        "portals/admin/polls/overview.html",
        {"poll": poll, "results": poll.get_results()},
    )


@admin_portal_required
@require_POST
def admin_poll_toggle(request, pk):
    poll = get_object_or_404(_admin_polls(request), pk=pk)
    poll.is_active = not poll.is_active
    poll.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "Poll publication status updated.")
    return redirect("admin_poll_detail", pk=poll.pk)


@admin_portal_required
def admin_poll_option_add(request, pk):
    poll = get_object_or_404(_admin_polls(request), pk=pk)
    form = PollOptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        option = form.save(commit=False)
        option.poll = poll
        option.save()
        messages.success(request, "Poll option added.")
        return redirect("admin_poll_detail", pk=poll.pk)
    return render(
        request,
        "portals/admin/polls/option_form.html",
        {"form": form, "poll": poll},
    )


@login_required
def poll_list(request):
    polls = polls_for_user(request)
    return render(
        request,
        "portals/polls/list.html",
        _portal_context(request, polls=polls),
    )


@login_required
def poll_detail(request, pk):
    poll = get_object_or_404(
        polls_for_user(request, include_closed=True).prefetch_related("options"),
        pk=pk,
    )
    vote = current_vote(poll, request)
    form = PollVoteForm(poll=poll)
    return render(
        request,
        "portals/polls/detail.html",
        _portal_context(
            request,
            poll=poll,
            vote=vote,
            form=form,
            can_vote=poll.is_available(),
            can_show_results=results_allowed(poll, request),
            results=poll.get_results(),
        ),
    )


@login_required
@require_POST
def poll_vote(request, pk):
    poll = get_object_or_404(polls_for_user(request).prefetch_related("options"), pk=pk)
    form = PollVoteForm(request.POST, poll=poll)
    previous_vote = current_vote(poll, request)
    if previous_vote and not poll.allow_multiple_votes:
        messages.warning(request, "You have already voted in this poll.")
        return redirect("poll_detail", pk=poll.pk)
    if form.is_valid():
        if previous_vote and poll.allow_multiple_votes:
            previous_vote.delete()
        option = form.cleaned_data["option"]
        PollVote.objects.create(
            poll=poll,
            option=option,
            user=None if poll.is_anonymous else request.user,
            ip_address=request_key(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
            voted_at=timezone.now(),
        )
        messages.success(request, "Vote recorded.")
    else:
        messages.error(request, "Please select an option.")
    return redirect("poll_detail", pk=poll.pk)


@login_required
def poll_results(request, pk):
    poll = get_object_or_404(
        polls_for_user(request, include_closed=True).prefetch_related("options"),
        pk=pk,
    )
    if not results_allowed(poll, request):
        messages.warning(request, "Results will be visible after you vote.")
        return redirect("poll_detail", pk=poll.pk)
    return render(
        request,
        "portals/polls/outcome.html",
        _portal_context(request, poll=poll, results=poll.get_results()),
    )
