"""
Roll Call View - Quick attendance marking interface
"""
import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .models import AttendanceEntry, AttendanceSession


@role_required(Role.TEACHER)
def roll_call(request):
    """
    Quick roll call interface for teachers.
    Displays students in order for rapid attendance marking.
    """
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    current_campus = get_current_campus(request)
    
    # Get teacher's offerings
    offerings = CourseOffering.objects.select_related(
        "course",
        "term",
        "term__year",
        "class_group",
    ).filter(teacher=teacher)
    
    if current_campus:
        offerings = offerings.filter(campus=current_campus)
    
    # Get selected offering and date
    offering_id = request.GET.get("offering")
    date_raw = request.GET.get("date")
    
    try:
        selected_date = (
            datetime.date.fromisoformat(date_raw) if date_raw else datetime.date.today()
        )
    except ValueError:
        selected_date = datetime.date.today()
    
    selected_offering = None
    students = []
    session = None
    existing_entries = {}
    
    if offering_id:
        selected_offering = offerings.filter(id=offering_id).first()
        
        if selected_offering:
            # Get enrolled students ordered by name
            enrollments = Enrollment.objects.select_related("student").filter(
                offering=selected_offering,
                status=Enrollment.ACTIVE
            ).order_by("student__last_name", "student__first_name")
            
            students = [e.student for e in enrollments]
            
            # Check for existing session
            session = AttendanceSession.objects.filter(
                offering=selected_offering,
                date=selected_date,
            ).first()
            
            if session:
                existing_entries = {
                    e.student_id: e.status
                    for e in AttendanceEntry.objects.filter(session=session)
                }
    
    return render(
        request,
        "portals/teacher/attendance/roll_call.html",
        {
            "teacher": teacher,
            "offerings": offerings,
            "selected_offering": selected_offering,
            "selected_date": selected_date,
            "students": students,
            "existing_entries": existing_entries,
            "STATUS_CHOICES": AttendanceEntry.STATUS_CHOICES,
        },
    )


@role_required(Role.TEACHER)
@require_POST
def roll_call_save(request):
    """
    AJAX endpoint to save roll call attendance quickly.
    Accepts JSON with student statuses.
    """
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return JsonResponse({"error": "No teacher profile"}, status=403)
    
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    offering_id = data.get("offering_id")
    date_str = data.get("date")
    attendance_data = data.get("attendance", {})  # {student_id: status}
    
    if not offering_id or not date_str:
        return JsonResponse({"error": "Missing offering or date"}, status=400)
    
    try:
        selected_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({"error": "Invalid date format"}, status=400)
    
    # Verify teacher owns this offering
    offering = CourseOffering.objects.filter(
        id=offering_id,
        teacher=teacher
    ).first()
    
    if not offering:
        return JsonResponse({"error": "Offering not found or not assigned to you"}, status=404)
    
    with transaction.atomic():
        # Create or get session
        session, created = AttendanceSession.objects.get_or_create(
            offering=offering,
            date=selected_date,
            defaults={"taken_by": teacher}
        )
        
        if session.taken_by_id is None:
            session.taken_by = teacher
            session.save(update_fields=["taken_by"])
        
        # Save attendance entries
        updated_count = 0
        for student_id_str, status in attendance_data.items():
            try:
                student_id = int(student_id_str)
            except (TypeError, ValueError):
                continue
            
            # Validate status
            valid_statuses = [choice[0] for choice in AttendanceEntry.STATUS_CHOICES]
            if status not in valid_statuses:
                continue
            
            AttendanceEntry.objects.update_or_create(
                session=session,
                student_id=student_id,
                defaults={"status": status}
            )
            updated_count += 1
    
    return JsonResponse({
        "success": True,
        "message": f"Attendance saved for {updated_count} student(s)",
        "session_id": session.id,
        "updated_count": updated_count
    })


@role_required(Role.TEACHER)
@require_POST
def roll_call_mark_student(request):
    """
    AJAX endpoint to mark a single student's attendance.
    For real-time updates during roll call.
    """
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return JsonResponse({"error": "No teacher profile"}, status=403)
    
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    offering_id = data.get("offering_id")
    date_str = data.get("date")
    student_id = data.get("student_id")
    status = data.get("status", AttendanceEntry.PRESENT)
    note = data.get("note", "")
    
    if not all([offering_id, date_str, student_id]):
        return JsonResponse({"error": "Missing required fields"}, status=400)
    
    try:
        selected_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({"error": "Invalid date format"}, status=400)
    
    # Verify teacher owns this offering
    offering = CourseOffering.objects.filter(
        id=offering_id,
        teacher=teacher
    ).first()
    
    if not offering:
        return JsonResponse({"error": "Offering not found"}, status=404)
    
    # Validate status
    valid_statuses = [choice[0] for choice in AttendanceEntry.STATUS_CHOICES]
    if status not in valid_statuses:
        return JsonResponse({"error": "Invalid status"}, status=400)
    
    with transaction.atomic():
        # Create or get session
        session, created = AttendanceSession.objects.get_or_create(
            offering=offering,
            date=selected_date,
            defaults={"taken_by": teacher}
        )
        
        if session.taken_by_id is None:
            session.taken_by = teacher
            session.save(update_fields=["taken_by"])
        
        # Save attendance entry
        entry, entry_created = AttendanceEntry.objects.update_or_create(
            session=session,
            student_id=student_id,
            defaults={"status": status, "note": note}
        )
    
    return JsonResponse({
        "success": True,
        "message": "Attendance marked",
        "student_id": student_id,
        "status": status,
        "created": entry_created
    })
