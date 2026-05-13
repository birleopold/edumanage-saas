from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Stream


@admin_portal_required
def stream_promotion(request):
    """
    Move all active students from one class stream to another (e.g. end-of-year promotion).
    Streams are limited to the active campus.
    """
    campus = get_current_campus(request)
    if not campus:
        messages.error(request, "Select a campus before running stream promotion.")
        return redirect("admin_orgsettings_campuses")

    streams = (
        Stream.objects.filter(is_active=True, class_group__campus=campus)
        .select_related("class_group")
        .order_by("class_group__name", "name")
    )

    if request.method == "POST":
        from_id = request.POST.get("from_stream")
        to_id = request.POST.get("to_stream")
        confirm = request.POST.get("confirm") == "1"

        if not from_id or not to_id:
            messages.error(request, "Choose both a source stream and a destination stream.")
        else:
            from_stream = get_object_or_404(
                Stream.objects.select_related("class_group"),
                pk=from_id,
                is_active=True,
                class_group__campus=campus,
            )
            to_stream = get_object_or_404(
                Stream.objects.select_related("class_group"),
                pk=to_id,
                is_active=True,
                class_group__campus=campus,
            )
            if from_stream.pk == to_stream.pk:
                messages.error(request, "Source and destination streams must be different.")
            elif not confirm:
                preview_count = StudentProfile.objects.filter(
                    stream=from_stream, is_active=True
                ).count()
                return render(
                    request,
                    "portals/admin/academics/stream_promotion.html",
                    {
                        "streams": streams,
                        "campus": campus,
                        "from_stream": from_stream,
                        "to_stream": to_stream,
                        "preview_count": preview_count,
                        "needs_confirm": True,
                    },
                )
            else:
                with transaction.atomic():
                    updated = StudentProfile.objects.filter(
                        stream=from_stream, is_active=True
                    ).update(stream=to_stream)
                messages.success(
                    request,
                    f"Moved {updated} active student(s) from {from_stream} to {to_stream}.",
                )
                return redirect("admin_stream_promotion")

    return render(
        request,
        "portals/admin/academics/stream_promotion.html",
        {"streams": streams, "campus": campus, "needs_confirm": False},
    )
