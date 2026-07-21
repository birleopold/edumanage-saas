from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required, role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Activity, ActivityMember
from .programme_forms import (
    ActivityAchievementForm,
    ActivityGroupForm,
    ActivityParticipationForm,
    ActivityProgrammeForm,
    ActivitySessionForm,
)
from .programme_models import (
    ActivityAttendance,
    ActivityGroup,
    ActivityParticipation,
    ActivityProgramme,
    ActivitySession,
)
from .programme_services import (
    activity_programme_readiness,
    bootstrap_activity_programmes,
    complete_activity_session,
    learner_co_curricular_summary,
    populate_session_attendance,
    update_attendance_entry,
)


def _activity_queryset_for(user):
    queryset = Activity.objects.select_related("campus", "head")
    campus = get_user_campus_scope(user)
    if campus:
        queryset = queryset.filter(Q(campus=campus) | Q(campus__isnull=True))
    return queryset


def _membership_queryset_for(user):
    queryset = ActivityMember.objects.select_related("activity", "student", "student__campus")
    campus = get_user_campus_scope(user)
    if campus:
        queryset = queryset.filter(student__campus=campus).filter(
            Q(activity__campus=campus) | Q(activity__campus__isnull=True)
        )
    return queryset


def _session_queryset_for(user):
    queryset = ActivitySession.objects.select_related("activity", "activity__campus", "group", "created_by")
    campus = get_user_campus_scope(user)
    if campus:
        queryset = queryset.filter(Q(activity__campus=campus) | Q(activity__campus__isnull=True))
    return queryset


@role_required(Role.ADMIN)
def programme_dashboard(request):
    if request.method == "POST" and request.POST.get("action") == "bootstrap":
        summary = bootstrap_activity_programmes(dry_run=False)
        messages.success(
            request,
            f"Programme profiles created: {summary['programme_created_count']}; "
            f"participation profiles created: {summary['participation_created_count']}. "
            "No activities, memberships, learners or finance records were changed.",
        )
        return redirect("admin_activity_programme_dashboard")

    rows = []
    for activity in _activity_queryset_for(request.user).order_by("name"):
        programme = ActivityProgramme.objects.filter(activity=activity).first()
        rows.append(
            {
                "activity": activity,
                "programme": programme,
                "member_count": activity.memberships.filter(is_active=True).count(),
                "group_count": programme.groups.filter(is_active=True).count() if programme else 0,
            }
        )
    return render(
        request,
        "portals/admin/activities/programme/dashboard.html",
        {
            "readiness": activity_programme_readiness(),
            "rows": rows,
            "recent_sessions": _session_queryset_for(request.user)[:8],
        },
    )


@admin_portal_required
def programme_edit(request, activity_pk):
    activity = get_object_or_404(_activity_queryset_for(request.user), pk=activity_pk)
    programme, _ = ActivityProgramme.objects.get_or_create(
        activity=activity,
        defaults={"code": f"ACTIVITY-{activity.pk}"},
    )
    if request.method == "POST":
        form = ActivityProgrammeForm(request.POST, instance=programme)
        if form.is_valid():
            form.save()
            messages.success(request, "Activity programme settings updated.")
            return redirect("admin_activity_programme_edit", activity_pk=activity.pk)
    else:
        form = ActivityProgrammeForm(instance=programme)
    return render(
        request,
        "portals/admin/activities/programme/programme_detail.html",
        {
            "activity": activity,
            "programme": programme,
            "form": form,
            "groups": programme.groups.select_related("coach"),
        },
    )


@admin_portal_required
def group_create(request, activity_pk):
    activity = get_object_or_404(_activity_queryset_for(request.user), pk=activity_pk)
    programme, _ = ActivityProgramme.objects.get_or_create(
        activity=activity,
        defaults={"code": f"ACTIVITY-{activity.pk}"},
    )
    if request.method == "POST":
        form = ActivityGroupForm(request.POST, programme=programme)
        if form.is_valid():
            group = form.save(commit=False)
            group.programme = programme
            group.save()
            messages.success(request, "Activity group created.")
            return redirect("admin_activity_programme_edit", activity_pk=activity.pk)
    else:
        form = ActivityGroupForm(programme=programme)
    return render(
        request,
        "portals/admin/activities/programme/form.html",
        {"form": form, "title": f"Add group to {activity}", "back_activity_pk": activity.pk},
    )


@admin_portal_required
def group_edit(request, pk):
    group = get_object_or_404(
        ActivityGroup.objects.select_related("programme", "programme__activity"),
        pk=pk,
        programme__activity__in=_activity_queryset_for(request.user),
    )
    if request.method == "POST":
        form = ActivityGroupForm(request.POST, instance=group, programme=group.programme)
        if form.is_valid():
            form.save()
            messages.success(request, "Activity group updated.")
            return redirect("admin_activity_programme_edit", activity_pk=group.programme.activity_id)
    else:
        form = ActivityGroupForm(instance=group, programme=group.programme)
    return render(
        request,
        "portals/admin/activities/programme/form.html",
        {"form": form, "title": f"Edit {group}", "back_activity_pk": group.programme.activity_id},
    )


@admin_portal_required
def participation_edit(request, member_pk):
    membership = get_object_or_404(_membership_queryset_for(request.user), pk=member_pk)
    programme, _ = ActivityProgramme.objects.get_or_create(
        activity=membership.activity,
        defaults={"code": f"ACTIVITY-{membership.activity_id}"},
    )
    participation, _ = ActivityParticipation.objects.get_or_create(
        membership=membership,
        defaults={
            "guardian_consent_status": (
                ActivityParticipation.PENDING
                if programme.guardian_consent_required
                else ActivityParticipation.NOT_REQUIRED
            ),
            "medical_clearance_status": (
                ActivityParticipation.PENDING
                if programme.medical_clearance_required
                else ActivityParticipation.NOT_REQUIRED
            ),
        },
    )
    if request.method == "POST":
        form = ActivityParticipationForm(
            request.POST,
            instance=participation,
            membership=membership,
        )
        if form.is_valid():
            item = form.save(commit=False)
            item.updated_by = request.user
            item.save()
            messages.success(request, "Participation profile updated.")
            return redirect("admin_activities_members", pk=membership.activity_id)
    else:
        form = ActivityParticipationForm(instance=participation, membership=membership)
    return render(
        request,
        "portals/admin/activities/programme/form.html",
        {"form": form, "title": f"Participation profile — {membership.student}", "back_members_activity_pk": membership.activity_id},
    )


@admin_portal_required
def session_list(request):
    q = (request.GET.get("q") or "").strip()
    queryset = _session_queryset_for(request.user)
    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(activity__name__icontains=q))
    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/activities/programme/sessions.html",
        {"sessions": page_obj.object_list, "page_obj": page_obj, "q": q},
    )


@admin_portal_required
def session_create(request):
    activities = _activity_queryset_for(request.user).filter(is_active=True)
    if request.method == "POST":
        form = ActivitySessionForm(request.POST, activity_queryset=activities)
        if form.is_valid():
            session = form.save(commit=False)
            session.created_by = request.user
            session.save()
            summary = populate_session_attendance(session, dry_run=False)
            messages.success(
                request,
                f"Session created with {summary['created_count']} unmarked participant(s).",
            )
            return redirect("admin_activity_session_detail", pk=session.pk)
    else:
        form = ActivitySessionForm(activity_queryset=activities)
    return render(
        request,
        "portals/admin/activities/programme/form.html",
        {"form": form, "title": "Create activity session", "back_sessions": True},
    )


@admin_portal_required
def session_detail(request, pk):
    session = get_object_or_404(
        _session_queryset_for(request.user).prefetch_related(
            "attendance_entries__membership__student"
        ),
        pk=pk,
    )
    if request.method == "POST" and session.status == ActivitySession.DRAFT:
        if request.POST.get("action") == "populate":
            try:
                summary = populate_session_attendance(session, dry_run=False)
                messages.success(request, f"Roster refreshed: {summary['created_count']} participant(s) added.")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
        else:
            for entry in session.attendance_entries.select_related("membership").all():
                status = request.POST.get(f"status_{entry.pk}")
                if status:
                    try:
                        update_attendance_entry(
                            entry,
                            status=status,
                            note=request.POST.get(f"note_{entry.pk}", ""),
                            user=request.user,
                        )
                    except ValidationError as exc:
                        messages.error(request, "; ".join(exc.messages))
            if request.POST.get("action") == "complete":
                try:
                    complete_activity_session(session)
                    messages.success(request, "Activity session completed.")
                except ValidationError as exc:
                    messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Attendance draft saved.")
        return redirect("admin_activity_session_detail", pk=session.pk)
    return render(
        request,
        "portals/admin/activities/programme/session_detail.html",
        {"session": session, "status_choices": ActivityAttendance.STATUS_CHOICES},
    )


@admin_portal_required
def achievement_create(request):
    memberships = _membership_queryset_for(request.user).filter(is_active=True)
    if request.method == "POST":
        form = ActivityAchievementForm(request.POST, membership_queryset=memberships)
        if form.is_valid():
            achievement = form.save(commit=False)
            achievement.recorded_by = request.user
            achievement.save()
            messages.success(request, "Co-curricular achievement recorded.")
            return redirect(
                "admin_activity_learner_summary",
                student_pk=achievement.membership.student_id,
            )
    else:
        form = ActivityAchievementForm(membership_queryset=memberships)
    return render(
        request,
        "portals/admin/activities/programme/form.html",
        {"form": form, "title": "Record co-curricular achievement", "back_dashboard": True},
    )


@admin_portal_required
def learner_summary(request, student_pk):
    students = StudentProfile.objects.select_related("campus")
    campus = get_user_campus_scope(request.user)
    if campus:
        students = students.filter(campus=campus)
    student = get_object_or_404(students, pk=student_pk)
    return render(
        request,
        "portals/admin/activities/programme/learner_summary.html",
        learner_co_curricular_summary(student),
    )
