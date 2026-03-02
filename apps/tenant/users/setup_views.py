from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import PasswordSetupToken, User


@require_http_methods(["GET", "POST"])
def password_setup(request, token: str):
    """Handle password setup via one-time token link."""
    setup_token = get_object_or_404(PasswordSetupToken, token=token)
    
    if not setup_token.is_valid():
        return render(
            request,
            "auth/setup_expired.html",
            {
                "used": setup_token.used_at is not None,
                "expired": True,
            },
        )
    
    if request.method == "POST":
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")
        
        if not password or len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(
                request,
                "auth/setup_password.html",
                {"token": token, "user": setup_token.user},
            )
        
        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(
                request,
                "auth/setup_password.html",
                {"token": token, "user": setup_token.user},
            )
        
        user = setup_token.user
        user.set_password(password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        
        setup_token.mark_used()
        
        login(request, user, backend="apps.tenant.users.backends.EmailOrUsernameModelBackend")
        messages.success(request, "Password set successfully! You are now logged in.")
        
        from apps.tenant.users.models import Role
        if user.has_role(Role.ADMIN) or user.has_role(Role.CAMPUS_ADMIN):
            return redirect("admin_home")
        elif user.has_role(Role.TEACHER):
            return redirect("teacher_home")
        elif user.has_role(Role.STUDENT):
            return redirect("student_home")
        elif user.has_role(Role.PARENT):
            return redirect("parent_home")
        
        return redirect("admin_home")
    
    return render(
        request,
        "auth/setup_password.html",
        {"token": token, "user": setup_token.user},
    )
