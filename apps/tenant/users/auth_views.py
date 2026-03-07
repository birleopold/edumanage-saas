"""
Enhanced authentication views with better UX.
"""
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    PasswordResetView,
    PasswordResetConfirmView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import (
    CustomLoginForm,
    CustomPasswordChangeForm,
    CustomPasswordResetConfirmForm,
    CustomPasswordResetForm,
    UserProfileForm,
)


class CustomLoginView(LoginView):
    """Enhanced login view with remember me functionality."""
    
    form_class = CustomLoginForm
    template_name = 'auth/login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        remember_me = form.cleaned_data.get('remember_me')
        
        if not remember_me:
            # Session expires when browser closes
            self.request.session.set_expiry(0)
        else:
            # Session expires after 2 weeks
            self.request.session.set_expiry(1209600)  # 2 weeks in seconds
        
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to appropriate portal based on user role."""
        user = self.request.user

        if getattr(user, "must_change_password", False):
            return reverse_lazy("change_password")
        
        # Check roles and redirect accordingly
        if hasattr(user, 'has_role'):
            from apps.tenant.users.models import Role
            
            if user.has_role(Role.ADMIN) or user.has_role(Role.CAMPUS_ADMIN):
                return reverse_lazy('admin_home')
            elif user.has_role(Role.TEACHER):
                return reverse_lazy('teacher_home')
            elif user.has_role(Role.STUDENT):
                return reverse_lazy('student_home')
            elif user.has_role(Role.PARENT):
                return reverse_lazy('parent_home')
        
        # Default fallback
        return reverse_lazy('admin_home')


class CustomPasswordResetView(PasswordResetView):
    """Enhanced password reset view."""
    
    form_class = CustomPasswordResetForm
    template_name = 'auth/password_reset.html'
    email_template_name = 'auth/password_reset_email.html'
    subject_template_name = 'auth/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    
    def form_valid(self, form):
        messages.success(
            self.request,
            'Password reset instructions have been sent to your email address.'
        )
        return super().form_valid(form)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Enhanced password reset confirmation view."""
    
    form_class = CustomPasswordResetConfirmForm
    template_name = 'auth/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    
    def form_valid(self, form):
        messages.success(
            self.request,
            'Your password has been reset successfully. You can now log in with your new password.'
        )
        return super().form_valid(form)


@login_required
def change_password(request):
    """Change password view."""
    
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            if getattr(user, "must_change_password", False):
                user.must_change_password = False
                user.save(update_fields=["must_change_password"])
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('user_profile')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'auth/change_password.html', {'form': form})


@login_required
def user_profile(request):
    """User profile view and edit."""
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('user_profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    # Get user roles
    user_roles = []
    if hasattr(request.user, 'roles'):
        user_roles = request.user.roles.all()
    
    context = {
        'form': form,
        'user_roles': user_roles,
    }
    
    return render(request, 'auth/profile.html', context)


@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    return redirect('login')
