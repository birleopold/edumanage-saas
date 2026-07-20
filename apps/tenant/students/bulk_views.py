import secrets

from django.contrib import messages
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization, get_current_campus
from apps.tenant.portals.permissions import admin_portal_required

from .bulk_import import (
    import_rows_from_serializable,
    import_rows_to_serializable,
    parse_csv_file,
    parse_excel_file,
    process_bulk_import,
    send_bulk_setup_emails,
)

BULK_IMPORT_SESSION_KEY = "student_bulk_import_preview_v2"
BULK_IMPORT_PREVIEW_TTL = 3600
BULK_IMPORT_CREDENTIALS_KEY = "bulk_import_credentials"
BULK_IMPORT_RESULT_KEY = "bulk_import_result_summary"


# Multipart uploads: browsers always send the file in the same form payload as
# other fields. Django's test Client must do the same and pass the uploaded file
# inside the data dictionary.


def _current_schema_name() -> str:
    return getattr(connection, "schema_name", "public") or "public"


def _store_preview(request, token: str, blob: dict) -> None:
    """Store one preview in the database-backed session shared by all workers."""

    request.session[BULK_IMPORT_SESSION_KEY] = {
        "token": token,
        "schema_name": _current_schema_name(),
        "expires_at": int(timezone.now().timestamp()) + BULK_IMPORT_PREVIEW_TTL,
        "blob": blob,
    }
    request.session.modified = True


def _clear_preview(request) -> None:
    if BULK_IMPORT_SESSION_KEY in request.session:
        del request.session[BULK_IMPORT_SESSION_KEY]
        request.session.modified = True


def _clear_previous_results(request) -> None:
    request.session.pop(BULK_IMPORT_CREDENTIALS_KEY, None)
    request.session.pop(BULK_IMPORT_RESULT_KEY, None)
    request.session.modified = True


def _load_preview(request, token: str):
    """Return the active preview only for the same user and tenant schema."""

    payload = request.session.get(BULK_IMPORT_SESSION_KEY)
    if not payload or payload.get("token") != token:
        return None

    if payload.get("schema_name") != _current_schema_name():
        _clear_preview(request)
        return None

    try:
        expires_at = int(payload.get("expires_at") or 0)
    except (TypeError, ValueError):
        expires_at = 0

    if expires_at <= int(timezone.now().timestamp()):
        _clear_preview(request)
        return None

    blob = payload.get("blob")
    if not isinstance(blob, dict) or blob.get("user_id") != request.user.pk:
        _clear_preview(request)
        return None

    return blob


@admin_portal_required
def bulk_import_students(request):
    """Bulk student import: preview rows, then confirm to commit."""

    org = get_or_create_organization()
    current_campus = get_current_campus(request)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()

        if action == "confirm":
            preview_token = (request.POST.get("preview_token") or "").strip()
            blob = _load_preview(request, preview_token) if preview_token else None
            if not blob:
                messages.error(
                    request,
                    "That import preview is no longer available. Please upload the file again.",
                )
                return redirect("admin_students_bulk_import")

            campuses = Campus.objects.filter(organization=org)
            campus_by_code = {campus.code: campus for campus in campuses if campus.code}
            campus_map = {}
            for code, pk in (blob.get("campus_map") or {}).items():
                try:
                    campus_map[code] = Campus.objects.get(pk=pk, organization=org)
                except Campus.DoesNotExist:
                    pass

            default_campus = campuses.filter(pk=blob["default_campus_id"]).first()
            if not default_campus:
                messages.error(request, "Default campus is no longer valid.")
                _clear_preview(request)
                return redirect("admin_students_bulk_import")

            rows = import_rows_from_serializable(blob["rows"])
            create_users = bool(blob.get("create_users"))
            send_emails = bool(blob.get("send_emails"))

            _clear_previous_results(request)
            result = process_bulk_import(
                rows=rows,
                default_campus=default_campus,
                campus_map=campus_map or campus_by_code,
                create_users=create_users,
                admin_user=request.user,
            )

            _clear_preview(request)
            request.session[BULK_IMPORT_RESULT_KEY] = {
                "successful": result.successful,
                "failed": result.failed,
            }

            if result.credentials:
                request.session[BULK_IMPORT_CREDENTIALS_KEY] = [
                    {
                        "student_id": credential["student"].pk,
                        "student_number": credential["username"],
                        "first_name": credential["student"].first_name,
                        "last_name": credential["student"].last_name,
                        "email": credential["student"].email,
                        "temp_password": credential["temp_password"],
                        "has_setup_token": bool(credential["setup_token"]),
                    }
                    for credential in result.credentials
                ]
            request.session.modified = True

            if result.errors:
                for error in result.errors[:10]:
                    messages.warning(request, error)
                if len(result.errors) > 10:
                    messages.warning(
                        request,
                        f"... and {len(result.errors) - 10} more errors",
                    )

            if result.successful > 0:
                messages.success(
                    request,
                    f"Successfully imported {result.successful} student(s). "
                    f"{result.failed} failed.",
                )
                if send_emails and result.credentials:
                    sent_count = send_bulk_setup_emails(
                        result.credentials,
                        request,
                        request.user,
                    )
                    if sent_count > 0:
                        messages.success(
                            request,
                            f"Setup emails sent to {sent_count} student(s).",
                        )
                if result.credentials:
                    return redirect("admin_students_bulk_import_results")
                return redirect("admin_students_list")

            messages.error(request, "Import failed. Please check the errors above.")
            return redirect("admin_students_bulk_import")

        uploaded_file = request.FILES.get("import_file")
        create_users = request.POST.get("create_users") == "on"
        send_emails = request.POST.get("send_emails") == "on"

        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("admin_students_bulk_import")

        campuses = Campus.objects.filter(organization=org)
        campus_map = {campus.code: campus for campus in campuses if campus.code}
        default_campus = current_campus or campuses.first()

        if not default_campus:
            messages.error(request, "No campus found. Please create a campus first.")
            return redirect("admin_students_bulk_import")

        filename = uploaded_file.name.lower()
        try:
            if filename.endswith(".csv"):
                rows = parse_csv_file(uploaded_file, campus_map)
            elif filename.endswith((".xlsx", ".xls")):
                rows = parse_excel_file(uploaded_file, campus_map)
            else:
                messages.error(
                    request,
                    "Invalid file format. Please upload CSV or Excel file.",
                )
                return redirect("admin_students_bulk_import")
        except Exception as exc:
            messages.error(request, f"Error parsing file: {str(exc)}")
            return redirect("admin_students_bulk_import")

        if not rows:
            messages.error(request, "No rows were found in the file.")
            return redirect("admin_students_bulk_import")

        valid_count = sum(1 for row in rows if row.is_valid())
        invalid_count = len(rows) - valid_count

        preview_token = secrets.token_urlsafe(32)
        campus_map_payload = {
            code: campus.pk for code, campus in campus_map.items()
        }
        _store_preview(
            request,
            preview_token,
            {
                "user_id": request.user.pk,
                "rows": import_rows_to_serializable(rows),
                "create_users": create_users,
                "send_emails": send_emails,
                "default_campus_id": default_campus.pk,
                "campus_map": campus_map_payload,
            },
        )

        return render(
            request,
            "portals/admin/students/bulk_import_preview.html",
            {
                "rows": rows,
                "preview_token": preview_token,
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "create_users": create_users,
                "send_emails": send_emails,
                "default_campus": default_campus,
                "current_campus": current_campus,
            },
        )

    return render(
        request,
        "portals/admin/students/bulk_import.html",
        {
            "current_campus": current_campus,
        },
    )


@admin_portal_required
def bulk_import_results(request):
    """Display bulk import results with download and print options."""

    credentials = request.session.get(BULK_IMPORT_CREDENTIALS_KEY, [])

    if not credentials:
        messages.info(request, "No import results available.")
        return redirect("admin_students_bulk_import")

    summary = request.session.get(
        BULK_IMPORT_RESULT_KEY,
        {"successful": len(credentials), "failed": 0},
    )
    return render(
        request,
        "portals/admin/students/bulk_import_results.html",
        {
            "credentials": credentials,
            "summary": summary,
        },
    )


@admin_portal_required
def print_bulk_credentials(request):
    """Render a standalone, credentials-only print sheet."""

    credentials = request.session.get(BULK_IMPORT_CREDENTIALS_KEY, [])
    if not credentials:
        messages.error(request, "No credentials are available to print.")
        return redirect("admin_students_bulk_import")

    organization = get_or_create_organization()
    campus = get_current_campus(request)
    return render(
        request,
        "portals/admin/students/bulk_credentials_print.html",
        {
            "credentials": credentials,
            "organization": organization,
            "campus": campus,
            "login_url": request.build_absolute_uri("/login/"),
            "printed_at": timezone.localtime(),
        },
    )


@admin_portal_required
def download_credentials_csv(request):
    """Download credentials as a CSV file."""

    credentials = request.session.get(BULK_IMPORT_CREDENTIALS_KEY, [])

    if not credentials:
        messages.error(request, "No credentials available for download.")
        return redirect("admin_students_bulk_import")

    import csv
    from datetime import datetime

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="student_credentials_'
        f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        ["Student Number", "First Name", "Last Name", "Email", "Temporary Password"]
    )

    for credential in credentials:
        writer.writerow(
            [
                credential["student_number"],
                credential["first_name"],
                credential["last_name"],
                credential["email"],
                credential["temp_password"],
            ]
        )

    return response


@admin_portal_required
def download_sample_template(request):
    """Download a sample CSV template for bulk import."""

    import csv

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="student_import_template.csv"'

    writer = csv.writer(response)
    writer.writerow(["first_name", "last_name", "date_of_birth", "email", "campus_code"])
    writer.writerow(["John", "Doe", "2010-05-15", "john.doe@example.com", "MAIN"])
    writer.writerow(["Jane", "Smith", "2011-08-22", "jane.smith@example.com", "BRANCH"])
    writer.writerow(["Bob", "Johnson", "2009-12-03", "", "MAIN"])

    return response
