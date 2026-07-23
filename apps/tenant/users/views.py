from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required

from .models import Role, User


@role_required(Role.ADMIN)
def user_list(request):
    q = (request.GET.get("q") or "").strip()
    selected_role = (request.GET.get("role") or "").strip().upper()
    selected_status = (request.GET.get("status") or "").strip().lower()
    per_page_raw = request.GET.get("per_page")
    page_number = request.GET.get("page") or 1

    users_qs = User.objects.all().prefetch_related("roles")
    if q:
        users_qs = users_qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
        )

    if selected_role:
        users_qs = users_qs.filter(roles__code=selected_role)

    if selected_status == "active":
        users_qs = users_qs.filter(is_active=True)
    elif selected_status == "inactive":
        users_qs = users_qs.filter(is_active=False)
    elif selected_status == "staff":
        users_qs = users_qs.filter(is_staff=True)
    elif selected_status == "setup":
        users_qs = users_qs.filter(must_change_password=True)

    per_page = 25
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = 25
    per_page = max(1, min(per_page, 200))

    users_qs = users_qs.distinct().order_by("username")
    paginator = Paginator(users_qs, per_page)
    page_obj = paginator.get_page(page_number)

    all_users = User.objects.all()
    needs_attention_count = all_users.filter(
        Q(is_active=False) | Q(must_change_password=True)
    ).distinct().count()

    return render(
        request,
        "portals/admin/users/list.html",
        {
            "users": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "roles": Role.objects.all().order_by("name", "code"),
            "selected_role": selected_role,
            "selected_status": selected_status,
            "total_users_count": all_users.count(),
            "active_users_count": all_users.filter(is_active=True).count(),
            "staff_users_count": all_users.filter(is_staff=True).count(),
            "needs_attention_count": needs_attention_count,
            "filtered_users_count": paginator.count,
        },
    )


@role_required(Role.ADMIN)
def user_roles_edit(request, pk: int):
    user_obj = get_object_or_404(User.objects.prefetch_related("roles"), pk=pk)
    roles = Role.objects.all().order_by("code")

    if request.method == "POST":
        role_ids = request.POST.getlist("role_ids")
        user_obj.roles.set(role_ids)
        messages.success(request, f"Access roles for {user_obj.username} were updated.")
        return redirect("admin_users_roles_edit", pk=user_obj.pk)

    selected_role_ids = set(user_obj.roles.values_list("id", flat=True))

    return render(
        request,
        "portals/admin/users/roles_edit.html",
        {
            "user_obj": user_obj,
            "roles": roles,
            "selected_role_ids": selected_role_ids,
        },
    )
