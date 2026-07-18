"""Roll Call View - Quick attendance marking interface."""
import datetime
import hashlib
import json

from django.core.cache import cache
from django.db import connection, transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .models import AttendanceEntry, AttendanceSession
from .services import (
    active_enrolled_students,
    active_teacher_offerings,
    get_or_create_attendance_session,
    save_attendance_entries,
    session_summary,
)


def _teacher_profile(request):
    return TeacherProfile.objects.filter(user=request.user).first()


def _parse_date(date_raw):
    try:
        return datetime.date.fromisoformat(date_raw) if date_raw else datetime.date.today()
    except ValueError:
        return datetime.date.today()


def _idempotency_cache_key(request):
    raw_key = (request.headers.get("X-Idempotency-Key") or "").strip()
    if not raw_key:
        return ""
    schema_name = getattr(connection, "schema_name", "default")
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"attendance-sync:{schema_name}:{request.user.pk}:{digest}"


@role_required(Role.TEACHER)
def roll_call(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    current_campus = get_current_campus(request)
    offerings = active_teacher_offerings(teacher)
    if current_campus:
        offerings = offerings.filter(campus=current_campus)

    offering_id = request.GET.get("offering")
    selected_date = _parse_date(request.GET.get("date"))
    selected_offering = offerings.filter(id=offering_id).first() if offering_id else None
    students = []
    session = None
    existing_entries = {}
    summary = None

    if selected_offering:
        students = list(active_enrolled_students(selected_offering))
        session = AttendanceSession.objects.filter(offering=selected_offering, date=selected_date).first()
        if session:
            existing_entries = {
                entry.student_id: entry.status
                for entry in AttendanceEntry.objects.filter(session=session)
            }
            summary = session_summary(session)

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
            "summary": summary,
            "STATUS_CHOICES": AttendanceEntry.STATUS_CHOICES,
        },
    )


@role_required(Role.TEACHER)
@require_POST
def roll_call_save(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return JsonResponse({"error": "No teacher profile"}, status=403)

    cache_key = _idempotency_cache_key(request)
    if cache_key:
        cached_response = cache.get(cache_key)
        if cached_response:
            return JsonResponse(cached_response)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    offering_id = data.get("offering_id")
    date_str = data.get("date")
    attendance_data = data.get("attendance", {})
    note_data = data.get("notes", {})

    if not offering_id or not date_str:
        return JsonResponse({"error": "Missing offering or date"}, status=400)
    if not isinstance(attendance_data, dict) or not isinstance(note_data, dict):
        return JsonResponse({"error": "Attendance and notes must be objects"}, status=400)

    try:
        selected_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    offering = active_teacher_offerings(teacher).filter(id=offering_id).first()
    if not offering:
        return JsonResponse({"error": "Offering not found or not assigned to you"}, status=404)

    with transaction.atomic():
        session = get_or_create_attendance_session(offering, selected_date, teacher)
        updated_count = save_attendance_entries(
            session=session,
            attendance_data=attendance_data,
            note_data=note_data,
            validate_enrollment=True,
        )

    response_payload = {
        "success": True,
        "message": f"Attendance saved for {updated_count} student(s)",
        "session_id": session.id,
        "updated_count": updated_count,
    }
    if cache_key:
        cache.set(cache_key, response_payload, timeout=24 * 60 * 60)
    return JsonResponse(response_payload)


@role_required(Role.TEACHER)
@require_POST
def roll_call_mark_student(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return JsonResponse({"error": "No teacher profile"}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
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

    offering = active_teacher_offerings(teacher).filter(id=offering_id).first()
    if not offering:
        return JsonResponse({"error": "Offering not found"}, status=404)

    with transaction.atomic():
        session = get_or_create_attendance_session(offering, selected_date, teacher)
        updated = save_attendance_entries(
            session=session,
            attendance_data={str(student_id): status},
            note_data={str(student_id): note},
            validate_enrollment=True,
        )

    if not updated:
        return JsonResponse({"error": "Student is not enrolled in this offering or status is invalid"}, status=400)

    return JsonResponse({"success": True, "message": "Attendance marked", "student_id": student_id, "status": status})
