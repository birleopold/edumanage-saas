import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from django.db import transaction

from apps.tenant.orgsettings.models import Campus


_SEQ_RE = re.compile(r"\{SEQ(?::(?P<padding>\d+))?\}")
_LEGACY_TRAILING_ZERO_RE = re.compile(r"(?P<zeros>0+)$")


@dataclass(frozen=True)
class StudentIdTokens:
    year: str
    campus_code: str
    seq: int
    padding: int


def _default_format() -> str:
    return "{CAMPUS_CODE}-{YYYY}-{SEQ:5}"


def _prepare_student_number_format(format_str: str) -> tuple[str, int]:
    """Return a sequence-aware format and any display offset.

    Schools commonly enter formats such as ``10/u/00`` expecting the trailing
    zeroes to count upwards. Treat that trailing zero run as a legacy sequence
    placeholder, where the first generated number remains ``00`` and later
    numbers become ``01``, ``02``, and so on.

    A literal custom format with no sequence marker receives a safe sequence
    suffix so it can never generate the same identifier repeatedly.
    """

    fmt = (format_str or "").strip() or _default_format()
    if _SEQ_RE.search(fmt):
        return fmt, 0

    legacy_match = _LEGACY_TRAILING_ZERO_RE.search(fmt)
    if legacy_match:
        padding = len(legacy_match.group("zeros"))
        prepared = f"{fmt[:legacy_match.start()]}{{SEQ:{padding}}}"
        return prepared, -1

    return f"{fmt}-{{SEQ:5}}", 0


def _render_student_id(format_str: str, tokens: StudentIdTokens) -> str:
    fmt = (format_str or "").strip() or _default_format()

    def _seq_repl(match: re.Match) -> str:
        padding_raw = match.group("padding")
        padding = int(padding_raw) if padding_raw else tokens.padding
        return str(tokens.seq).zfill(padding)

    fmt = fmt.replace("{YYYY}", tokens.year)
    fmt = fmt.replace("{CAMPUS_CODE}", tokens.campus_code)
    fmt = _SEQ_RE.sub(_seq_repl, fmt)
    return fmt


def _student_number_exists(student_number: str) -> bool:
    """Check both profile identifiers and login usernames for a collision."""

    from apps.tenant.users.models import User

    from .models import StudentProfile

    return (
        StudentProfile.objects.filter(student_id__iexact=student_number).exists()
        or User.objects.filter(username__iexact=student_number).exists()
    )


def generate_next_student_id(campus: Optional[Campus], today: Optional[date] = None) -> str:
    if campus is None:
        raise ValueError("Campus is required to generate a student number")

    today = today or date.today()

    with transaction.atomic():
        locked = Campus.objects.select_for_update().get(pk=campus.pk)
        campus_code = (locked.code or str(locked.pk)).strip() or str(locked.pk)
        format_str, display_offset = _prepare_student_number_format(
            locked.student_number_format
        )

        while True:
            locked.last_student_sequence = (locked.last_student_sequence or 0) + 1
            sequence = locked.last_student_sequence
            display_sequence = max(sequence + display_offset, 0)
            candidate = _render_student_id(
                format_str,
                StudentIdTokens(
                    year=str(today.year),
                    campus_code=campus_code,
                    seq=display_sequence,
                    padding=5,
                ),
            )

            if len(candidate) > 64:
                raise ValueError(
                    "Generated student number exceeds 64 characters. "
                    "Please shorten the campus student-number format."
                )

            if not _student_number_exists(candidate):
                locked.save(update_fields=["last_student_sequence"])
                return candidate


def sync_student_user(student):
    """Keep the login identity aligned with the authoritative learner profile.

    StudentProfile remains the source of truth for a learner's name and email.
    Names and role assignment must never fail because of an older conflicting
    account email; in that case the existing login email is retained for an
    administrator to resolve separately.
    """

    if not getattr(student, "user_id", None):
        return None

    from apps.tenant.users.models import Role, User

    user = student.user
    desired_first_name = (student.first_name or "").strip()
    desired_last_name = (student.last_name or "").strip()
    desired_email = (student.email or "").strip().lower()

    changed_fields = []
    if user.first_name != desired_first_name:
        user.first_name = desired_first_name
        changed_fields.append("first_name")
    if user.last_name != desired_last_name:
        user.last_name = desired_last_name
        changed_fields.append("last_name")

    email_available = not desired_email or not User.objects.filter(
        email__iexact=desired_email
    ).exclude(pk=user.pk).exists()
    if email_available and user.email != desired_email:
        user.email = desired_email
        changed_fields.append("email")

    if changed_fields:
        user.save(update_fields=changed_fields)

    student_role, _ = Role.objects.get_or_create(
        code=Role.STUDENT,
        defaults={"name": "Student"},
    )
    user.roles.add(student_role)
    return user
