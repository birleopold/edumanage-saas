import secrets

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization, get_current_campus
from apps.tenant.portals.permissions import admin_portal_required

from .bulk_import import (
    generate_credentials_pdf,
    import_rows_from_serializable,
    import_rows_to_serializable,
    parse_csv_file,
    parse_excel_file,
    process_bulk_import,
    send_bulk_setup_emails,
)

BULK_IMPORT_CACHE_PREFIX = "student_bulk_import_v1:"
BULK_IMPORT_CACHE_TTL = 3600

# Multipart uploads: browsers always send the file in the same form payload as other fields.
# Django 5's test Client must do the same — pass the file on the `data` dict (e.g.
# `post(url, {"action": "preview", "import_file": file})`). Using a separate `files=`
# kwarg can leave `request.FILES` empty in tests.

def _bulk_cache_key(token: str) -> str:
    return f"{BULK_IMPORT_CACHE_PREFIX}{token}"


@admin_portal_required
def bulk_import_students(request):
    """Bulk student import: preview rows, then confirm to commit."""
    org = get_or_create_organization()
    current_campus = get_current_campus(request)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()

        if action == "confirm":
            preview_token = (request.POST.get("preview_token") or "").strip()
            blob = cache.get(_bulk_cache_key(preview_token)) if preview_token else None
            if not blob or blob.get("user_id") != request.user.pk:
                messages.error(
                    request,
                    "That import preview is no longer available. Please upload the file again.",
                )
                return redirect("admin_students_bulk_import")

            campuses = Campus.objects.filter(organization=org)
            campus_by_code = {
                c.code: c for c in campuses if c.code
            }
            campus_map = {}
            for code, pk in (blob.get("campus_map") or {}).items():
                try:
                    campus_map[code] = Campus.objects.get(pk=pk, organization=org)
                except Campus.DoesNotExist:
                    pass

            default_campus = campuses.filter(pk=blob["default_campus_id"]).first()
            if not default_campus:
                messages.error(request, "Default campus is no longer valid.")
                cache.delete(_bulk_cache_key(preview_token))
                return redirect("admin_students_bulk_import")

            rows = import_rows_from_serializable(blob["rows"])
            create_users = bool(blob.get("create_users"))
            send_emails = bool(blob.get("send_emails"))

            result = process_bulk_import(
                rows=rows,
                default_campus=default_campus,
                campus_map=campus_map or campus_by_code,
                create_users=create_users,
                admin_user=request.user,
            )

            cache.delete(_bulk_cache_key(preview_token))

            if result.credentials:
                request.session["bulk_import_credentials"] = [
                    {
                        "student_id": c["student"].pk,
                        "student_number": c["username"],
                        "first_name": c["student"].first_name,
                        "last_name": c["student"].last_name,
                        "email": c["student"].email,
                        "temp_password": c["temp_password"],
                        "has_setup_token": bool(c["setup_token"]),
                    }
                    for c in result.credentials
                ]

            if result.errors:
                for error in result.errors[:10]:
                    messages.warning(request, error)
                if len(result.errors) > 10:
                    messages.warning(request, f"... and {len(result.errors) - 10} more errors")

            if result.successful > 0:
                messages.success(
                    request,
                    f"Successfully imported {result.successful} student(s). "
                    f"{result.failed} failed.",
                )
                if send_emails and result.credentials:
                    sent_count = send_bulk_setup_emails(result.credentials, request, request.user)
                    if sent_count > 0:
                        messages.success(request, f"Setup emails sent to {sent_count} student(s).")
                return redirect("admin_students_bulk_import_results")

            messages.error(request, "Import failed. Please check the errors above.")
            return redirect("admin_students_bulk_import")

        # Preview path
        uploaded_file = request.FILES.get("import_file")
        create_users = request.POST.get("create_users") == "on"
        send_emails = request.POST.get("send_emails") == "on"

        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("admin_students_bulk_import")

        campuses = Campus.objects.filter(organization=org)
        campus_map = {c.code: c for c in campuses if c.code}
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
        except Exception as e:
            messages.error(request, f"Error parsing file: {str(e)}")
            return redirect("admin_students_bulk_import")

        if not rows:
            messages.error(request, "No valid rows found in the file.")
            return redirect("admin_students_bulk_import")

        valid_n = sum(1 for r in rows if r.is_valid())
        invalid_n = len(rows) - valid_n

        preview_token = secrets.token_urlsafe(32)
        campus_map_payload = {code: c.pk for code, c in campus_map.items()}
        cache.set(
            _bulk_cache_key(preview_token),
            {
                "user_id": request.user.pk,
                "rows": import_rows_to_serializable(rows),
                "create_users": create_users,
                "send_emails": send_emails,
                "default_campus_id": default_campus.pk,
                "campus_map": campus_map_payload,
            },
            BULK_IMPORT_CACHE_TTL,
        )

        return render(
            request,
            "portals/admin/students/bulk_import_preview.html",
            {
                "rows": rows,
                "preview_token": preview_token,
                "valid_count": valid_n,
                "invalid_count": invalid_n,
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
    """Display bulk import results with download options."""
    credentials = request.session.get("bulk_import_credentials", [])

    if not credentials:
        messages.info(request, "No import results available.")
        return redirect("admin_students_bulk_import")

    return render(
        request,
        "portals/admin/students/bulk_import_results.html",
        {
            "credentials": credentials,
        },
    )


@admin_portal_required
def download_credentials_csv(request):
    """Download credentials as CSV file."""
    credentials = request.session.get("bulk_import_credentials", [])

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
    writer.writerow(["Student Number", "First Name", "Last Name", "Email", "Temporary Password"])

    for cred in credentials:
        writer.writerow(
            [
                cred["student_number"],
                cred["first_name"],
                cred["last_name"],
                cred["email"],
                cred["temp_password"],
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
