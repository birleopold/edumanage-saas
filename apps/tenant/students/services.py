import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from django.db import transaction

from apps.tenant.orgsettings.models import Campus


_SEQ_RE = re.compile(r"\{SEQ(?::(?P<padding>\d+))?\}")


@dataclass(frozen=True)
class StudentIdTokens:
    year: str
    campus_code: str
    seq: int
    padding: int


def _default_format() -> str:
    return "{CAMPUS_CODE}-{YYYY}-{SEQ:5}"


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


def generate_next_student_id(campus: Optional[Campus], today: Optional[date] = None) -> str:
    if campus is None:
        raise ValueError("Campus is required to generate a student number")

    today = today or date.today()

    with transaction.atomic():
        locked = Campus.objects.select_for_update().get(pk=campus.pk)
        locked.last_student_sequence = (locked.last_student_sequence or 0) + 1
        seq = locked.last_student_sequence
        locked.save(update_fields=["last_student_sequence"])

    campus_code = (locked.code or str(locked.pk)).strip() or str(locked.pk)

    tokens = StudentIdTokens(
        year=str(today.year),
        campus_code=campus_code,
        seq=seq,
        padding=5,
    )
    return _render_student_id(locked.student_number_format, tokens)
