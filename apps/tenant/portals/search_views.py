"""
Cross-module search for admin portal (students, staff, parents, invoices,
applicants, grievances, fee catalog items, and users when not campus-scoped).
"""
from django.db.models import Q
from django.shortcuts import render

from apps.tenant.admissions.models import Applicant
from apps.tenant.finance.models import FeeItem, Invoice
from apps.tenant.grievances.models import Grievance
from apps.tenant.parents.models import ParentProfile
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import User


def _q(request):
    return (request.GET.get("q") or "").strip()


@admin_portal_required
def global_search(request):
    query = _q(request)
    scoped = get_user_campus_scope(request.user)

    students = StudentProfile.objects.select_related("campus").none()
    teachers = TeacherProfile.objects.select_related("campus").none()
    parents = ParentProfile.objects.none()
    invoices = Invoice.objects.select_related("student", "student__campus").none()
    applicants = Applicant.objects.select_related("campus").none()
    grievances = Grievance.objects.select_related("campus", "submitted_by").none()
    fee_items = FeeItem.objects.none()
    users = User.objects.none()

    if len(query) >= 2:
        sq = (
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(student_id__icontains=query)
            | Q(email__icontains=query)
        )
        students = StudentProfile.objects.select_related("campus").filter(sq)
        if scoped:
            students = students.filter(campus=scoped)
        students = students[:15]

        tq = (
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(staff_id__icontains=query)
            | Q(email__icontains=query)
        )
        teachers = TeacherProfile.objects.select_related("campus").filter(tq)
        if scoped:
            teachers = teachers.filter(campus=scoped)
        teachers = teachers[:15]

        pq = (
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
        parents = ParentProfile.objects.filter(pq)
        if scoped:
            parents = parents.filter(parentstudentlink__student__campus=scoped).distinct()
        parents = parents[:15]

        iq = (
            Q(reference__icontains=query)
            | Q(student__first_name__icontains=query)
            | Q(student__last_name__icontains=query)
            | Q(student__student_id__icontains=query)
        )
        invoices = Invoice.objects.select_related("student", "student__campus").filter(iq)
        if scoped:
            invoices = invoices.filter(student__campus=scoped)
        invoices = invoices[:15]

        aq = (
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
        )
        applicants = Applicant.objects.select_related("campus").filter(aq)
        if scoped:
            applicants = applicants.filter(Q(campus=scoped) | Q(campus__isnull=True))
        applicants = applicants[:15]

        gq = Q(subject__icontains=query) | Q(body__icontains=query)
        grievances = Grievance.objects.select_related("campus", "submitted_by").filter(gq)
        if scoped:
            grievances = grievances.filter(Q(campus=scoped) | Q(campus__isnull=True))
        grievances = grievances.order_by("-created_at")[:15]

        fee_items = FeeItem.objects.filter(
            Q(name__icontains=query) | Q(code__icontains=query),
            is_active=True,
        )[:15]

        if scoped is None:
            users = User.objects.filter(
                Q(username__icontains=query) | Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )[:10]

    return render(
        request,
        "portals/admin/global_search.html",
        {
            "q": query,
            "students": list(students),
            "teachers": list(teachers),
            "parents": list(parents),
            "invoices": list(invoices),
            "applicants": list(applicants),
            "grievances": list(grievances),
            "fee_items": list(fee_items),
            "users": list(users),
            "scoped_campus": scoped,
        },
    )
