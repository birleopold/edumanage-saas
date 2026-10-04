from django import forms
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from .models import PlatformStaffAccess
from .platform_permissions import platform_can
from .platform_views import platform_admin_required
User=get_user_model()
class StaffForm(forms.Form):
    user=forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by("username"))
    role=forms.ChoiceField(choices=PlatformStaffAccess.ROLE_CHOICES)
@platform_admin_required
def staff_list(request):
    if not platform_can(request.user,"lifecycle"): return redirect("platform_access_denied")
    form=StaffForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        PlatformStaffAccess.objects.update_or_create(user=form.cleaned_data["user"],defaults={"role":form.cleaned_data["role"],"is_active":True})
        messages.success(request,"Platform staff access saved.")
        return redirect("platform_staff")
    return render(request,"platform/staff.html",{"form":form,"staff":PlatformStaffAccess.objects.select_related("user").order_by("user__username")})
@platform_admin_required
@require_POST
def staff_disable(request,pk):
    if not platform_can(request.user,"lifecycle"): return redirect("platform_access_denied")
    access=PlatformStaffAccess.objects.filter(pk=pk).first()
    if access and access.user_id!=request.user.id:
        access.is_active=False; access.save(update_fields=["is_active","updated_at"])
        messages.success(request,"Platform staff access disabled.")
    elif access:
        messages.error(request,"You cannot disable your own Platform access.")
    return redirect("platform_staff")
