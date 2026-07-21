from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import (
    ClassGroupPathwayAssignment,
    ProgrammePathway,
    ProgrammePathwayLevel,
    SubjectCombination,
    SubjectCombinationCourse,
)
from .pathway_forms import (
    ClassGroupPathwayAssignmentForm,
    OfferingPlanForm,
    ProgrammePathwayForm,
    ProgrammePathwayLevelForm,
    SubjectCombinationCourseForm,
    SubjectCombinationForm,
)
from .pathway_services import (
    assignment_errors,
    bootstrap_programme_pathways,
    combination_errors,
    create_missing_offerings,
    offering_plan,
    pathway_errors,
    pathway_framework_readiness,
)


def _form_page(request, *, form, title, back_url):
    return render(
        request,
        "portals/admin/academics/pathways/form.html",
        {"form": form, "title": title, "back_url": back_url},
    )


@role_required(Role.ADMIN)
def pathway_dashboard(request):
    if request.method == "POST" and request.POST.get("action") == "bootstrap":
        summary = bootstrap_programme_pathways(dry_run=False)
        messages.success(
            request,
            "Pathway bootstrap complete: "
            f"{summary['pathways_created']} pathway(s), "
            f"{summary['combinations_created']} combination(s), "
            f"{summary['levels_created']} level link(s), and "
            f"{summary['courses_linked']} course link(s) created. "
            "No class groups, students, offerings or enrollments were changed.",
        )
        return redirect("admin_pathway_dashboard")

    readiness = pathway_framework_readiness()
    pathways = ProgrammePathway.objects.select_related("program", "campus", "stage").prefetch_related(
        "pathway_levels__level",
        "subject_combinations__course_memberships__course",
    )
    pathway_rows = [
        {"pathway": pathway, "errors": pathway_errors(pathway)}
        for pathway in pathways
    ]
    assignments = ClassGroupPathwayAssignment.objects.select_related(
        "class_group",
        "class_group__campus",
        "class_group__level",
        "class_group__program",
        "pathway",
        "subject_combination",
        "academic_term",
        "academic_term__year",
    ).prefetch_related(
        "pathway__pathway_levels__level",
        "pathway__subject_combinations__course_memberships__course",
        "subject_combination__course_memberships__course",
    )
    assignment_rows = [
        {"assignment": assignment, "errors": assignment_errors(assignment)}
        for assignment in assignments
    ]
    return render(
        request,
        "portals/admin/academics/pathways/dashboard.html",
        {
            "readiness": readiness,
            "pathway_rows": pathway_rows,
            "assignment_rows": assignment_rows,
        },
    )


@role_required(Role.ADMIN)
def pathway_create(request):
    if request.method == "POST":
        form = ProgrammePathwayForm(request.POST)
        if form.is_valid():
            pathway = form.save()
            messages.success(request, "Programme pathway created. Add its ordered levels next.")
            return redirect("admin_pathway_detail", pk=pathway.pk)
    else:
        form = ProgrammePathwayForm()
    return _form_page(
        request,
        form=form,
        title="Add programme pathway",
        back_url=reverse("admin_pathway_dashboard"),
    )


@role_required(Role.ADMIN)
def pathway_edit(request, pk: int):
    pathway = get_object_or_404(ProgrammePathway, pk=pk)
    if request.method == "POST":
        form = ProgrammePathwayForm(request.POST, instance=pathway)
        if form.is_valid():
            form.save()
            messages.success(request, "Programme pathway updated.")
            return redirect("admin_pathway_detail", pk=pathway.pk)
    else:
        form = ProgrammePathwayForm(instance=pathway)
    return _form_page(
        request,
        form=form,
        title=f"Edit pathway — {pathway.name}",
        back_url=reverse("admin_pathway_detail", args=[pathway.pk]),
    )


@role_required(Role.ADMIN)
def pathway_detail(request, pk: int):
    pathway = get_object_or_404(
        ProgrammePathway.objects.select_related("program", "campus", "stage").prefetch_related(
            "pathway_levels__level",
            "subject_combinations__course_memberships__course",
        ),
        pk=pk,
    )
    combinations = pathway.subject_combinations.select_related("level").prefetch_related(
        "course_memberships__course"
    )
    combination_rows = [
        {"combination": combination, "errors": combination_errors(combination)}
        for combination in combinations
    ]
    return render(
        request,
        "portals/admin/academics/pathways/pathway_detail.html",
        {
            "pathway": pathway,
            "pathway_errors": pathway_errors(pathway),
            "levels": pathway.pathway_levels.select_related("level"),
            "combination_rows": combination_rows,
        },
    )


@role_required(Role.ADMIN)
def pathway_level_create(request, pathway_pk: int):
    pathway = get_object_or_404(ProgrammePathway, pk=pathway_pk)
    if request.method == "POST":
        form = ProgrammePathwayLevelForm(request.POST, pathway=pathway)
        if form.is_valid():
            form.save()
            messages.success(request, "Pathway level added.")
            return redirect("admin_pathway_detail", pk=pathway.pk)
    else:
        form = ProgrammePathwayLevelForm(pathway=pathway)
    return _form_page(
        request,
        form=form,
        title=f"Add level — {pathway.name}",
        back_url=reverse("admin_pathway_detail", args=[pathway.pk]),
    )


@role_required(Role.ADMIN)
def pathway_level_edit(request, pk: int):
    item = get_object_or_404(ProgrammePathwayLevel.objects.select_related("pathway", "level"), pk=pk)
    if request.method == "POST":
        form = ProgrammePathwayLevelForm(request.POST, instance=item, pathway=item.pathway)
        if form.is_valid():
            form.save()
            messages.success(request, "Pathway level updated.")
            return redirect("admin_pathway_detail", pk=item.pathway_id)
    else:
        form = ProgrammePathwayLevelForm(instance=item, pathway=item.pathway)
    return _form_page(
        request,
        form=form,
        title=f"Edit pathway level — {item.level}",
        back_url=reverse("admin_pathway_detail", args=[item.pathway_id]),
    )


@role_required(Role.ADMIN)
def combination_create(request, pathway_pk: int):
    pathway = get_object_or_404(ProgrammePathway, pk=pathway_pk)
    if request.method == "POST":
        form = SubjectCombinationForm(request.POST, pathway=pathway)
        if form.is_valid():
            combination = form.save()
            messages.success(request, "Subject combination created. Add its courses next.")
            return redirect("admin_combination_detail", pk=combination.pk)
    else:
        form = SubjectCombinationForm(pathway=pathway)
    return _form_page(
        request,
        form=form,
        title=f"Add subject combination — {pathway.name}",
        back_url=reverse("admin_pathway_detail", args=[pathway.pk]),
    )


@role_required(Role.ADMIN)
def combination_edit(request, pk: int):
    combination = get_object_or_404(SubjectCombination.objects.select_related("pathway", "level"), pk=pk)
    if request.method == "POST":
        form = SubjectCombinationForm(request.POST, instance=combination, pathway=combination.pathway)
        if form.is_valid():
            form.save()
            messages.success(request, "Subject combination updated.")
            return redirect("admin_combination_detail", pk=combination.pk)
    else:
        form = SubjectCombinationForm(instance=combination, pathway=combination.pathway)
    return _form_page(
        request,
        form=form,
        title=f"Edit subject combination — {combination.name}",
        back_url=reverse("admin_combination_detail", args=[combination.pk]),
    )


@role_required(Role.ADMIN)
def combination_detail(request, pk: int):
    combination = get_object_or_404(
        SubjectCombination.objects.select_related("pathway", "level", "pathway__program").prefetch_related(
            "course_memberships__course"
        ),
        pk=pk,
    )
    return render(
        request,
        "portals/admin/academics/pathways/combination_detail.html",
        {
            "combination": combination,
            "combination_errors": combination_errors(combination),
            "memberships": combination.course_memberships.select_related("course"),
        },
    )


@role_required(Role.ADMIN)
def combination_course_create(request, combination_pk: int):
    combination = get_object_or_404(SubjectCombination.objects.select_related("pathway"), pk=combination_pk)
    if request.method == "POST":
        form = SubjectCombinationCourseForm(request.POST, combination=combination)
        if form.is_valid():
            form.save()
            messages.success(request, "Course added to the subject combination.")
            return redirect("admin_combination_detail", pk=combination.pk)
    else:
        form = SubjectCombinationCourseForm(combination=combination)
    return _form_page(
        request,
        form=form,
        title=f"Add course — {combination.name}",
        back_url=reverse("admin_combination_detail", args=[combination.pk]),
    )


@role_required(Role.ADMIN)
def combination_course_edit(request, pk: int):
    membership = get_object_or_404(
        SubjectCombinationCourse.objects.select_related("combination", "combination__pathway", "course"),
        pk=pk,
    )
    if request.method == "POST":
        form = SubjectCombinationCourseForm(
            request.POST,
            instance=membership,
            combination=membership.combination,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Combination course updated.")
            return redirect("admin_combination_detail", pk=membership.combination_id)
    else:
        form = SubjectCombinationCourseForm(instance=membership, combination=membership.combination)
    return _form_page(
        request,
        form=form,
        title=f"Edit combination course — {membership.course}",
        back_url=reverse("admin_combination_detail", args=[membership.combination_id]),
    )


@role_required(Role.ADMIN)
def pathway_assignment_create(request):
    if request.method == "POST":
        form = ClassGroupPathwayAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pathway assignment created. Existing class-group and learner records were not changed.")
            return redirect("admin_pathway_dashboard")
    else:
        form = ClassGroupPathwayAssignmentForm()
    return _form_page(
        request,
        form=form,
        title="Assign pathway to class group",
        back_url=reverse("admin_pathway_dashboard"),
    )


@role_required(Role.ADMIN)
def pathway_assignment_edit(request, pk: int):
    assignment = get_object_or_404(ClassGroupPathwayAssignment, pk=pk)
    if request.method == "POST":
        form = ClassGroupPathwayAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, "Pathway assignment updated.")
            return redirect("admin_pathway_dashboard")
    else:
        form = ClassGroupPathwayAssignmentForm(instance=assignment)
    return _form_page(
        request,
        form=form,
        title=f"Edit pathway assignment — {assignment.class_group}",
        back_url=reverse("admin_pathway_dashboard"),
    )


@role_required(Role.ADMIN)
def pathway_offerings(request):
    initial = {}
    if request.GET.get("class_group"):
        initial["class_group"] = request.GET.get("class_group")
    if request.GET.get("term"):
        initial["term"] = request.GET.get("term")

    plan = None
    if request.method == "POST":
        form = OfferingPlanForm(request.POST)
        if form.is_valid():
            class_group = form.cleaned_data["class_group"]
            term = form.cleaned_data["term"]
            if request.POST.get("action") == "create":
                result = create_missing_offerings(class_group, term, dry_run=False)
                messages.success(
                    request,
                    f"Created {result['created_count']} missing offering(s); "
                    f"{result['existing_count']} existing offering(s) were preserved.",
                )
                query = urlencode({"class_group": class_group.pk, "term": term.pk})
                return redirect(f"{reverse('admin_pathway_offerings')}?{query}")
            plan = offering_plan(class_group, term)
    else:
        form = OfferingPlanForm(initial=initial)
        if initial.get("class_group") and initial.get("term") and form.is_valid():
            plan = offering_plan(form.cleaned_data["class_group"], form.cleaned_data["term"])

    return render(
        request,
        "portals/admin/academics/pathways/offerings.html",
        {"form": form, "plan": plan},
    )
