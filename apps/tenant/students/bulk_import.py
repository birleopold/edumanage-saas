import csv
import io
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import List, Optional

from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.utils import log_action
from apps.tenant.users.models import Role, User, PasswordSetupToken

from .models import StudentProfile
from .services import generate_next_student_id


IMPORT_DATE_ERROR = (
    "Invalid date format (use YYYY-MM-DD, MM/DD/YYYY, or DD/MM/YYYY)"
)
IMPORT_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


@dataclass
class ImportRow:
    """Represents a single row from the import file."""

    row_number: int
    first_name: str
    last_name: str
    date_of_birth: Optional[str]
    email: Optional[str]
    campus_code: Optional[str]
    errors: List[str]

    def is_valid(self) -> bool:
        return len(self.errors) == 0


def import_rows_to_serializable(rows: List[ImportRow]) -> list:
    """JSON-serializable payloads for import preview storage."""

    return [asdict(row) for row in rows]


def import_rows_from_serializable(data: list) -> List[ImportRow]:
    """Restore ImportRow objects from import_rows_to_serializable()."""

    rows: List[ImportRow] = []
    for item in data:
        rows.append(
            ImportRow(
                row_number=int(item["row_number"]),
                first_name=str(item.get("first_name") or ""),
                last_name=str(item.get("last_name") or ""),
                date_of_birth=item.get("date_of_birth"),
                email=item.get("email"),
                campus_code=item.get("campus_code"),
                errors=list(item.get("errors") or []),
            )
        )
    return rows


@dataclass
class ImportResult:
    """Result of a bulk import operation."""

    total_rows: int
    successful: int
    failed: int
    students: List[StudentProfile]
    credentials: List[dict]
    errors: List[str]


def _clean_cell(value) -> str:
    """Return a trimmed string without turning blank spreadsheet cells into 'None'."""

    if value is None:
        return ""
    return str(value).strip()


def normalize_import_date(value, *, excel_epoch=None) -> Optional[str]:
    """Normalize common CSV/Excel date values to the ISO format used by Django."""

    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    if excel_epoch is not None and isinstance(value, (int, float)):
        try:
            from openpyxl.utils.datetime import from_excel

            converted = from_excel(value, epoch=excel_epoch)
            if isinstance(converted, datetime):
                return converted.date().isoformat()
            if isinstance(converted, date):
                return converted.isoformat()
        except (TypeError, ValueError, OverflowError):
            return None

    text = _clean_cell(value)
    if not text:
        return None

    for date_format in IMPORT_DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _normalized_csv_row(row: dict) -> dict:
    return {
        _clean_cell(key).lower(): _clean_cell(value)
        for key, value in row.items()
        if key is not None
    }


def parse_csv_file(file, campus_map: dict) -> List[ImportRow]:
    """Parse an uploaded CSV file, normalize dates, and validate each row."""

    rows = []
    content = file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    for idx, raw_row in enumerate(reader, start=2):
        row = _normalized_csv_row(raw_row)
        errors = []

        first_name = row.get("first_name", "")
        last_name = row.get("last_name", "")
        raw_date_of_birth = row.get("date_of_birth", "")
        email = row.get("email", "")
        campus_code = row.get("campus_code", "")

        if not first_name:
            errors.append("First name is required")
        if not last_name:
            errors.append("Last name is required")

        date_of_birth = normalize_import_date(raw_date_of_birth)
        if raw_date_of_birth and not date_of_birth:
            errors.append(IMPORT_DATE_ERROR)

        if campus_code and campus_code not in campus_map:
            errors.append(f"Campus code '{campus_code}' not found")

        rows.append(
            ImportRow(
                row_number=idx,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                email=email or None,
                campus_code=campus_code or None,
                errors=errors,
            )
        )

    return rows


def parse_excel_file(file, campus_map: dict) -> List[ImportRow]:
    """Parse an uploaded Excel file, normalize dates, and validate each row."""

    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError(
            "openpyxl is required for Excel file support. Install with: pip install openpyxl"
        ) from exc

    rows = []
    workbook = openpyxl.load_workbook(file, data_only=True, read_only=True)
    sheet = workbook.active
    headers = [_clean_cell(cell.value).lower() for cell in sheet[1]]

    try:
        for idx, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            row = dict(zip(headers, values))
            errors = []

            first_name = _clean_cell(row.get("first_name"))
            last_name = _clean_cell(row.get("last_name"))
            raw_date_of_birth = row.get("date_of_birth")
            email = _clean_cell(row.get("email"))
            campus_code = _clean_cell(row.get("campus_code"))

            if not first_name:
                errors.append("First name is required")
            if not last_name:
                errors.append("Last name is required")

            date_of_birth = normalize_import_date(
                raw_date_of_birth,
                excel_epoch=workbook.epoch,
            )
            if raw_date_of_birth not in (None, "") and not date_of_birth:
                errors.append(IMPORT_DATE_ERROR)

            if campus_code and campus_code not in campus_map:
                errors.append(f"Campus code '{campus_code}' not found")

            rows.append(
                ImportRow(
                    row_number=idx,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=date_of_birth,
                    email=email or None,
                    campus_code=campus_code or None,
                    errors=errors,
                )
            )
    finally:
        workbook.close()

    return rows


def process_bulk_import(
    rows: List[ImportRow],
    default_campus: Campus,
    campus_map: dict,
    create_users: bool,
    admin_user: User,
) -> ImportResult:
    """Process validated import rows and create students with credentials."""

    students = []
    credentials = []
    errors = []
    successful = 0
    failed = 0

    for row in rows:
        if not row.is_valid():
            failed += 1
            errors.append(f"Row {row.row_number}: {', '.join(row.errors)}")
            continue

        try:
            with transaction.atomic():
                campus = (
                    campus_map.get(row.campus_code, default_campus)
                    if row.campus_code
                    else default_campus
                )
                student_id = generate_next_student_id(campus)

                user = None
                temp_password = None
                setup_token = None

                if create_users:
                    temp_password = User.objects.make_random_password(length=12)
                    user = User.objects.create(
                        username=student_id,
                        email=row.email or "",
                    )
                    user.set_password(temp_password)
                    user.must_change_password = True
                    user.save(update_fields=["password", "must_change_password"])

                    student_role = Role.objects.filter(code=Role.STUDENT).first()
                    if student_role:
                        user.roles.add(student_role)

                    if row.email:
                        setup_token = PasswordSetupToken.create_for_user(
                            user,
                            created_by=admin_user,
                        )

                student = StudentProfile.objects.create(
                    user=user,
                    campus=campus,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    date_of_birth=row.date_of_birth,
                    student_id=student_id,
                    email=row.email or "",
                    is_active=True,
                )

                log_action(
                    student,
                    action="BULK_IMPORT",
                    description=f"Student created via bulk import (row {row.row_number}).",
                    user=admin_user,
                    metadata={
                        "row_number": row.row_number,
                        "has_user": bool(user),
                        "has_email": bool(row.email),
                    },
                )

                students.append(student)
                if create_users:
                    credentials.append(
                        {
                            "student": student,
                            "username": student_id,
                            "temp_password": temp_password,
                            "setup_token": setup_token,
                        }
                    )

                successful += 1

        except Exception as exc:
            failed += 1
            errors.append(f"Row {row.row_number}: {str(exc)}")

    return ImportResult(
        total_rows=len(rows),
        successful=successful,
        failed=failed,
        students=students,
        credentials=credentials,
        errors=errors,
    )


def generate_credentials_pdf(credentials: List[dict], request) -> HttpResponse:
    """Generate a PDF with all credentials for printing."""

    from weasyprint import HTML

    html_content = render_to_string(
        "portals/admin/students/bulk_credentials_pdf.html",
        {"credentials": credentials},
    )

    pdf = HTML(
        string=html_content,
        base_url=request.build_absolute_uri("/"),
    ).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        'attachment; filename="student_credentials_'
        f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    )
    return response


def send_bulk_setup_emails(credentials: List[dict], request, admin_user: User):
    """Send setup emails to imported students that have email addresses."""

    sent_count = 0

    for credential in credentials:
        student = credential["student"]
        setup_token = credential["setup_token"]

        if not student.email or not setup_token:
            continue

        setup_url = request.build_absolute_uri(f"/users/setup/{setup_token.token}/")

        try:
            send_mail(
                subject="Set Up Your Student Portal Account",
                message=(
                    f"Hello {student.first_name},\n\n"
                    f"Your student number: {student.student_id}\n\n"
                    f"Click the link below to set your password:\n{setup_url}\n\n"
                    "This link is valid for 72 hours and can only be used once.\n\n"
                    "If you did not request this, please contact your administrator."
                ),
                from_email=None,
                recipient_list=[student.email],
                fail_silently=False,
            )

            log_action(
                student,
                action="CREDENTIALS_ISSUED",
                description="Student setup link sent via bulk email.",
                user=admin_user,
                metadata={
                    "delivery": "email_secure_link_bulk",
                    "username": student.student_id,
                },
            )

            sent_count += 1
        except Exception:
            pass

    return sent_count
