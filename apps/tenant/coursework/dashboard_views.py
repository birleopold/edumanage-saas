from django.shortcuts import render
from django.utils import timezone

from apps.tenant.portals.permissions import admin_portal_required

from .models import Assignment, AssignmentSubmission, CourseworkComment, LearningMaterial


@admin_portal_required
def coursework_dashboard(request):
    now = timezone.now()
    recent_materials = (
        LearningMaterial.objects.select_related("campus", "class_group", "stream", "offering")
        .prefetch_related("attachments")
        .order_by("-publish_at", "-created_at")[:8]
    )
    recent_assignments = (
        Assignment.objects.select_related("campus", "class_group", "stream", "offering")
        .prefetch_related("attachments", "submissions")
        .order_by("-publish_at", "-created_at")[:8]
    )

    context = {
        "material_count": LearningMaterial.objects.count(),
        "active_material_count": LearningMaterial.objects.filter(is_active=True).count(),
        "assignment_count": Assignment.objects.count(),
        "active_assignment_count": Assignment.objects.filter(is_active=True).count(),
        "submitted_count": AssignmentSubmission.objects.filter(submitted_at__isnull=False).count(),
        "marked_count": AssignmentSubmission.objects.filter(marked_at__isnull=False).count(),
        "overdue_assignment_count": Assignment.objects.filter(
            is_active=True,
            due_date__isnull=False,
            due_date__lt=now,
        ).count(),
        "comment_count": CourseworkComment.objects.count(),
        "recent_materials": recent_materials,
        "recent_assignments": recent_assignments,
    }
    return render(request, "portals/admin/coursework/dashboard.html", context)
