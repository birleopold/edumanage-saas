from django.contrib import admin

from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    Level,
    Program,
)


admin.site.register(AcademicYear)
admin.site.register(AcademicTerm)
admin.site.register(Level)
admin.site.register(Program)
admin.site.register(ClassGroup)
admin.site.register(Course)
admin.site.register(CourseOffering)
admin.site.register(Enrollment)
