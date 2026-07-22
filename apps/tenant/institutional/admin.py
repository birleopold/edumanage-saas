from django.contrib import admin

from .models import (
    CandidateDossier,
    CandidateExamAttendance,
    CandidateMockCycle,
    ECDObservation,
    LearnerSubjectCombination,
    MealAttendance,
    MealService,
    ReportTemplate,
    ResultPolicy,
    StudentProperty,
    VerifiablePermit,
    VisitationWindow,
    VisitorRecord,
)


for model in (
    ReportTemplate,
    ResultPolicy,
    ECDObservation,
    LearnerSubjectCombination,
    CandidateDossier,
    CandidateMockCycle,
    CandidateExamAttendance,
    VerifiablePermit,
    VisitationWindow,
    VisitorRecord,
    MealService,
    MealAttendance,
    StudentProperty,
):
    admin.site.register(model)
