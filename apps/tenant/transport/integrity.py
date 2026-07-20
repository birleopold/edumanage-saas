from django.db.models import Count, F, Q
from django.utils import timezone

from apps.tenant.orgsettings.integrity import IntegrityIssue

from .models import StudentTransportAssignment, TransportRoute, VehicleTracking


def audit_transport_integrity() -> list[IntegrityIssue]:
    """Return read-only transport integrity findings for the active tenant schema."""

    issues: list[IntegrityIssue] = []

    duplicate_active_students = list(
        StudentTransportAssignment.objects.filter(is_active=True)
        .values("student_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if duplicate_active_students:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "MULTIPLE_ACTIVE_TRANSPORT_ASSIGNMENTS",
                len(duplicate_active_students),
                "Students have more than one active transport assignment.",
                tuple(
                    f"student_id={row['student_id']}, count={row['total']}"
                    for row in duplicate_active_students[:5]
                ),
            )
        )

    stop_route_mismatches = list(
        StudentTransportAssignment.objects.exclude(stop__isnull=True)
        .exclude(stop__route_id=F("route_id"))
        .values("id", "student_id", "route_id", "stop_id", "stop__route_id")
        .order_by("id")
    )
    if stop_route_mismatches:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "TRANSPORT_STOP_ROUTE_MISMATCH",
                len(stop_route_mismatches),
                "Transport assignments use stops that belong to another route.",
                tuple(
                    "assignment={id}, student={student_id}, route={route_id}, stop={stop_id}, stop_route={stop__route_id}".format(
                        **row
                    )
                    for row in stop_route_mismatches[:5]
                ),
            )
        )

    inactive_route_assignments = StudentTransportAssignment.objects.filter(
        is_active=True,
        route__is_active=False,
    ).count()
    if inactive_route_assignments:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "ACTIVE_ASSIGNMENT_INACTIVE_ROUTE",
                inactive_route_assignments,
                "Active transport assignments point to inactive routes.",
            )
        )

    inactive_stop_assignments = StudentTransportAssignment.objects.filter(
        is_active=True,
        stop__isnull=False,
        stop__is_active=False,
    ).count()
    if inactive_stop_assignments:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "ACTIVE_ASSIGNMENT_INACTIVE_STOP",
                inactive_stop_assignments,
                "Active transport assignments point to inactive stops.",
            )
        )

    expired_active_assignments = StudentTransportAssignment.objects.filter(
        is_active=True,
        end_date__lt=timezone.localdate(),
    ).count()
    if expired_active_assignments:
        issues.append(
            IntegrityIssue(
                "WARNING",
                "EXPIRED_ACTIVE_TRANSPORT_ASSIGNMENT",
                expired_active_assignments,
                "Transport assignments remain active after their end date.",
            )
        )

    over_capacity_routes = list(
        TransportRoute.objects.filter(vehicle__isnull=False)
        .annotate(
            active_assignments=Count(
                "student_assignments",
                filter=Q(student_assignments__is_active=True),
            )
        )
        .filter(active_assignments__gt=F("vehicle__capacity"))
        .values("id", "code", "vehicle__capacity", "active_assignments")
        .order_by("-active_assignments")
    )
    if over_capacity_routes:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "TRANSPORT_ROUTE_OVER_CAPACITY",
                len(over_capacity_routes),
                "Active transport assignments exceed vehicle capacity.",
                tuple(
                    f"route={row['id']} {row['code']!r}, capacity={row['vehicle__capacity']}, active={row['active_assignments']}"
                    for row in over_capacity_routes[:5]
                ),
            )
        )

    tracking_mismatches = VehicleTracking.objects.filter(
        route__isnull=False,
        route__vehicle__isnull=False,
    ).exclude(vehicle_id=F("route__vehicle_id")).count()
    if tracking_mismatches:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "TRACKING_ROUTE_VEHICLE_MISMATCH",
                tracking_mismatches,
                "Vehicle tracking records reference a route assigned to another vehicle.",
            )
        )

    return sorted(issues, key=lambda item: (0 if item.severity == "ERROR" else 1, item.code))
