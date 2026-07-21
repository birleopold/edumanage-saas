from django.contrib import messages
from django.shortcuts import render

from .clearance_services import evaluate_clearance


def clearance_gate(request, student, access_type: str, *, academic_term=None):
    """Return (decision, response). A response is returned only for a blocking decision."""
    decision = evaluate_clearance(student, access_type, academic_term=academic_term)
    if decision.advisory:
        messages.warning(request, decision.message)
        return decision, None
    if decision.blocked:
        response = render(
            request,
            "portals/shared/finance_clearance_gate.html",
            {
                "student": student,
                "clearance_decision": decision,
                "clearance_policy": decision.policy,
                "finance_summary": decision.finance,
            },
            status=403,
        )
        return decision, response
    return decision, None
