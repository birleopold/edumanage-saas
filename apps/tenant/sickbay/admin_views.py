from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.orgsettings.models import Notification
from apps.tenant.parents.models import ParentStudentLink
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .forms import SickbayVisitForm, StudentMedicalProfileForm
from .models import SickbayVisit, StudentMedicalProfile


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    try:
        return max(1, min(int(request.GET.get("per_page", default)), max_value))
    except (TypeError, ValueError):
        return default


def _notify_linked_parents(visit: SickbayVisit, created_by=None) -> int:
    if not visit.parent_notified:
        return 0
    parent_links = ParentStudentLink.objects.filter(student=visit.student, parent__user__isnull=False).select_related("parent__user")
    count = 0
    for link in parent_links:
        Notification.objects.create(
            recipient=link.parent.user,
            audience=Notification.PARENTS,
            campus=visit.campus,
            title=f"Sickbay visit: {visit.student}",
            message=f"{visit.student} visited the sickbay for {visit.complaint}. Outcome: {visit.get_outcome_display()}.",
            priority=Notification.URGENT if visit.severity == SickbayVisit.SEVERE else Notification.NORMAL,
            link=reverse("parent_sickbay_visits"),
            created_by=created_by,
        )
        count += 1
    return count


def _visit_queryset_for(user):
    qs = SickbayVisit.objects.select_related("student", "campus", "attended_by_user", "created_by")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _profile_queryset_for(user):
    qs = StudentMedicalProfile.objects.select_related("student", "student__campus")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(student__campus=scoped)
    return qs


def _can_access_student_campus(user, student) -> bool:
    scoped = get_user_campus_scope(user)
    return scoped is None or student.campus_id == scoped.id


@admin_portal_required
def sickbay_dashboard(request):
    today = timezone.localdate()
    visits_qs = _visit_queryset_for(request.user)
    profiles_qs = _profile_queryset_for(request.user)
    visits_today = visits_qs.filter(visit_at__date=today)
    open_followups = visits_qs.filter(follow_up_required=True).exclude(
        outcome__in=[SickbayVisit.RETURNED_TO_CLASS, SickbayVisit.SENT_HOME, SickbayVisit.REFERRED]
    )
    recent_visits = visits_qs.order_by("-visit_at")[:10]
    outcome_rows = visits_qs.values("outcome").annotate(count=Count("id")).order_by("-count")[:6]
    return render(
        request,
        "portals/admin/sickbay/dashboard.html",
        {
            "visits_today_count": visits_today.count(),
            "parent_notified_today_count": visits_today.filter(parent_notified=True).count(),
            "follow_up_count": open_followups.count(),
            "profile_alert_count": profiles_qs.filter(
                Q(allergies__gt="") | Q(chronic_conditions__gt="") | Q(current_medication__gt="")
            ).count(),
            "recent_visits": recent_visits,
            "outcome_rows": outcome_rows,
        },
    )


@admin_portal_required
def visit_list(request):
    q = (request.GET.get("q") or "").strip()
    outcome = (request.GET.get("outcome") or "").strip()
    per_page = _parse_per_page(request)
    qs = _visit_queryset_for(request.user)
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(complaint__icontains=q)
            | Q(symptoms__icontains=q)
        )
    if outcome:
        qs = qs.filter(outcome=outcome)
    page_obj = Paginator(qs, per_page).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/sickbay/visit_list.html",
        {
            "visits": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "outcome": outcome,
            "outcome_choices": SickbayVisit.OUTCOME_CHOICES,
            "per_page": per_page,
        },
    )


@admin_portal_required
def visit_create(request):
    scoped = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = SickbayVisitForm(request.POST, campus_scope=scoped)
        if form.is_valid():
            visit = form.save(commit=False)
            if not _can_access_student_campus(request.user, visit.student):
                return HttpResponseForbidden("You cannot record sickbay visits outside your campus scope.")
            visit.created_by = request.user
            visit.attended_by_user = request.user
            visit.save()
            notified = _notify_linked_parents(visit, created_by=request.user)
            suffix = f" {notified} parent portal notification(s) created." if notified else ""
            messages.success(request, f"Sickbay visit recorded.{suffix}")
            return redirect("admin_sickbay_visit_detail", pk=visit.pk)
    else:
        form = SickbayVisitForm(campus_scope=scoped)
    return render(request, "portals/admin/sickbay/visit_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def visit_edit(request, pk: int):
    visit = get_object_or_404(_visit_queryset_for(request.user), pk=pk)
    scoped = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = SickbayVisitForm(request.POST, instance=visit, campus_scope=scoped)
        if form.is_valid():
            if not _can_access_student_campus(request.user, form.cleaned_data["student"]):
                return HttpResponseForbidden("You cannot move sickbay visits outside your campus scope.")
            form.save()
            messages.success(request, "Sickbay visit updated.")
            return redirect("admin_sickbay_visit_detail", pk=visit.pk)
    else:
        form = SickbayVisitForm(instance=visit, campus_scope=scoped)
    return render(request, "portals/admin/sickbay/visit_form.html", {"form": form, "mode": "edit", "visit": visit})


@admin_portal_required
def visit_detail(request, pk: int):
    visit = get_object_or_404(
        _visit_queryset_for(request.user).select_related("student__medical_profile"),
        pk=pk,
    )
    profile = getattr(visit.student, "medical_profile", None)
    return render(request, "portals/admin/sickbay/visit_detail.html", {"visit": visit, "profile": profile})


@admin_portal_required
def medical_profile_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = _profile_queryset_for(request.user)
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(allergies__icontains=q)
            | Q(chronic_conditions__icontains=q)
        )
    page_obj = Paginator(qs, _parse_per_page(request)).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/sickbay/profile_list.html",
        {"profiles": page_obj.object_list, "page_obj": page_obj, "q": q},
    )


@admin_portal_required
def medical_profile_create(request):
    scoped = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = StudentMedicalProfileForm(request.POST, campus_scope=scoped)
        if form.is_valid():
            if not _can_access_student_campus(request.user, form.cleaned_data["student"]):
                return HttpResponseForbidden("You cannot create medical profiles outside your campus scope.")
            profile = form.save()
            messages.success(request, "Medical profile saved.")
            return redirect("admin_sickbay_profile_edit", pk=profile.pk)
    else:
        form = StudentMedicalProfileForm(campus_scope=scoped)
    return render(request, "portals/admin/sickbay/profile_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def medical_profile_edit(request, pk: int):
    profile = get_object_or_404(_profile_queryset_for(request.user), pk=pk)
    scoped = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = StudentMedicalProfileForm(request.POST, instance=profile, campus_scope=scoped)
        if form.is_valid():
            if not _can_access_student_campus(request.user, form.cleaned_data["student"]):
                return HttpResponseForbidden("You cannot move medical profiles outside your campus scope.")
            form.save()
            messages.success(request, "Medical profile updated.")
            return redirect("admin_sickbay_profile_edit", pk=profile.pk)
    else:
        form = StudentMedicalProfileForm(instance=profile, campus_scope=scoped)
    return render(request, "portals/admin/sickbay/profile_form.html", {"form": form, "mode": "edit", "profile": profile})
