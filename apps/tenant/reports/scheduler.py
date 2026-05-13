"""
Generate scheduled / on-demand CSV reports (operational overview).
"""
import csv
from datetime import date
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .models import ReportRun


def execute_overview_csv_run(
    *,
    triggered_by,
    start: date,
    end: date,
    campus_id: Optional[int],
) -> ReportRun:
    """
    Build overview metrics CSV (same rows as Reports overview export) under MEDIA_ROOT/generated_reports/.
    """
    from apps.tenant.reports.admin_views import _compute_metrics

    try:
        metrics = _compute_metrics(start, end, campus_id)
        media_dir = Path(settings.MEDIA_ROOT) / "generated_reports"
        media_dir.mkdir(parents=True, exist_ok=True)
        fn = f"overview_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = media_dir / fn
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            for row in metrics:
                w.writerow(list(row))
        rel = f"generated_reports/{fn}"
        return ReportRun.objects.create(
            report_type=ReportRun.OVERVIEW_CSV,
            status=ReportRun.STATUS_SUCCESS,
            triggered_by=triggered_by,
            file_path=rel,
        )
    except Exception as exc:
        return ReportRun.objects.create(
            report_type=ReportRun.OVERVIEW_CSV,
            status=ReportRun.STATUS_FAILED,
            triggered_by=triggered_by,
            detail=str(exc)[:4000],
        )
