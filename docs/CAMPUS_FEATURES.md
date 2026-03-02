# Campus-Aware Features Documentation

## Overview
The EduManage SaaS system now supports comprehensive multi-campus operations with data integrity, permissions, and enhanced UI/UX.

## Features

### 1. Campus-Aware Data Models
All core models include campus foreign keys:
- `StudentProfile.campus`
- `TeacherProfile.campus`
- `ClassGroup.campus`
- `CourseOffering.campus`
- `Enrollment.campus`

### 2. Data Validation & Integrity

#### Model-Level Validation
- **CourseOffering**: Validates campus consistency with `class_group` and `teacher`
- **Enrollment**: Validates campus consistency with `offering` and `student`
- Auto-derives campus from related objects when not specified
- `save()` methods call `full_clean()` to enforce validation

#### Management Commands
```bash
# Check campus data integrity
python manage.py check_campus_integrity
python manage.py check_campus_integrity --fix

# Fix campus data issues
python manage.py fix_campus_data
python manage.py fix_campus_data --dry-run
```

### 3. Bulk Operations

#### Bulk Enrollment
```python
from apps.tenant.academics.bulk_operations import bulk_enroll_students

result = bulk_enroll_students(
    offering=offering,
    student_ids=[1, 2, 3],
    validate_campus=True
)
print(f"Created: {result.success_count}, Errors: {result.error_count}")
```

#### Campus Transfer
```python
from apps.tenant.academics.bulk_operations import (
    bulk_transfer_students_campus,
    bulk_transfer_teachers_campus
)

# Transfer students
success, errors = bulk_transfer_students_campus(
    student_ids=[1, 2, 3],
    target_campus=campus,
    update_enrollments=True
)

# Transfer teachers
success, errors = bulk_transfer_teachers_campus(
    teacher_ids=[1, 2],
    target_campus=campus,
    update_offerings=True
)
```

#### Bulk Offering Creation
```python
from apps.tenant.academics.bulk_operations import bulk_create_offerings_for_campus

success, errors = bulk_create_offerings_for_campus(
    course_ids=[1, 2, 3],
    term_id=1,
    campus=campus,
    class_group_id=1,
    teacher_id=1
)
```

### 4. Campus-Level Permissions

#### Roles
- **ADMIN**: Global admin with access to all campuses
- **CAMPUS_ADMIN**: Campus-scoped admin with access to only their assigned campus
- **TEACHER**, **STUDENT**, **PARENT**: Standard roles with natural campus scoping

#### Assign Campus Admin Role
```bash
# Assign campus admin
python manage.py assign_campus_admin <username> <campus_id>

# Remove campus admin
python manage.py assign_campus_admin <username> <campus_id> --remove
```

#### Permission Utilities
```python
from apps.tenant.portals.campus_permissions import (
    get_user_campus_scope,
    user_can_access_campus,
    enforce_campus_scope,
    get_accessible_campuses,
)

# Get user's campus restriction
campus = get_user_campus_scope(user)  # None for global admins

# Check access
can_access = user_can_access_campus(user, campus)

# Filter queryset by campus scope
filtered_qs = enforce_campus_scope(queryset, user, campus_field='campus')

# Get accessible campuses
campuses = get_accessible_campuses(user)
```

#### Decorators
```python
from apps.tenant.portals.campus_permissions import campus_admin_required

@campus_admin_required
def my_view(request):
    # Only accessible by ADMIN or CAMPUS_ADMIN
    pass
```

### 5. Campus Dashboard & Metrics

#### Get Campus Metrics
```python
from apps.tenant.orgsettings.campus_dashboard import (
    get_campus_metrics,
    get_all_campuses_summary,
    compare_campuses
)

# Single campus metrics
metrics = get_campus_metrics(campus, date_range_days=30)
# Returns: students, teachers, enrollments, attendance, finance stats

# All campuses summary
summary = get_all_campuses_summary()

# Compare campuses
comparison = compare_campuses([1, 2, 3], date_range_days=30)
```

### 6. UI/UX Enhancements

#### CSS Styling
Include campus UI styles in templates:
```html
{% load static %}
<link rel="stylesheet" href="{% static 'css/campus-ui.css' %}">
```

#### Template Tags
```html
{% load campus_tags %}

<!-- Campus badge -->
{% campus_badge student.campus %}
{% campus_badge offering.campus show_all_text=True %}

<!-- Campus filter dropdown -->
{% campus_filter campuses selected_campus_id %}

<!-- Campus indicator for page headers -->
{% campus_indicator current_campus %}

<!-- Template filters -->
{{ student.campus|campus_display }}
<span class="campus-badge {{ campus|campus_class }}">
```

#### CSS Classes Available
- `.campus-badge` - Campus badge component
- `.campus-filter-form` - Campus filter dropdown
- `.campus-switcher` - Header campus switcher
- `.campus-info-card` - Campus information card
- `.campus-stats` - Campus statistics grid
- `.campus-stat-card` - Individual stat card
- `.campus-comparison` - Campus comparison grid
- `.page-campus-indicator` - Page header campus indicator

### 7. Portal Features

#### Admin Portal
- Campus selector in header (all campuses or specific campus)
- Campus-filtered lists for students, teachers, offerings, enrollments
- Campus-aware dashboard with metrics
- Campus comparison view

#### Teacher Portal
- Campus filter on attendance and exams pages
- Defaults to teacher's campus
- Can view "All Campuses" if needed

#### Parent Portal
- Campus selector to filter children by campus
- Campus-grouped children display
- Campus-filtered invoices, incidents, library, transport, documents

#### Student Portal
- Displays student's campus on all pages
- Naturally scoped to student's campus
- No campus selector needed (students belong to one campus)

### 8. Session Management

#### Current Campus Selection
The system maintains a "current campus" in the user's session:
```python
from apps.tenant.orgsettings.services import (
    get_current_campus,
    set_current_campus,
    update_current_campus_from_request,
    selected_campus_id_from_request
)

# Get current campus from session
campus = get_current_campus(request)

# Set current campus
set_current_campus(request, campus)

# Update from request (GET param: ?campus=123 or ?campus= for "All")
update_current_campus_from_request(request)

# Get selected campus ID (None means "All")
campus_id = selected_campus_id_from_request(request)
```

### 9. Data Integrity Rules

1. **Enrollment Campus** must match:
   - Offering campus (if both set)
   - Student campus (if both set)

2. **Offering Campus** must match:
   - Class group campus (if both set)
   - Teacher campus (if both set)

3. **Auto-derivation**:
   - Enrollment campus derived from offering or student if not set
   - Offering campus derived from class_group if not set

4. **Validation on Save**:
   - All models call `full_clean()` before saving
   - ValidationError raised for campus mismatches

## Migration Path

### For Existing Data
1. Run integrity check:
   ```bash
   python manage.py check_campus_integrity
   ```

2. Fix issues automatically:
   ```bash
   python manage.py fix_campus_data
   ```

3. Or preview changes first:
   ```bash
   python manage.py fix_campus_data --dry-run
   ```

### For New Installations
1. Create campuses via admin interface
2. Set default campus in organization settings
3. Assign campus admins as needed
4. Campus fields will auto-populate based on relationships

## Best Practices

1. **Always validate campus consistency** when creating related objects
2. **Use bulk operations** for mass updates to ensure atomicity
3. **Check user campus scope** before filtering data in views
4. **Use template tags** for consistent campus display
5. **Test with both global and campus admins** to ensure proper scoping
6. **Run integrity checks** after bulk imports or migrations

## API Examples

### Creating Campus-Aware Records
```python
# Create offering with campus
offering = CourseOffering(
    course=course,
    term=term,
    campus=campus,
    class_group=class_group,  # Must be same campus
    teacher=teacher  # Must be same campus
)
offering.save()  # Validates campus consistency

# Create enrollment
enrollment = Enrollment(
    offering=offering,
    student=student,  # Must be same campus as offering
    campus=offering.campus  # Or auto-derived
)
enrollment.save()  # Validates campus consistency
```

### Filtering by Campus Scope
```python
from apps.tenant.portals.campus_permissions import enforce_campus_scope

# In a view
students = StudentProfile.objects.all()
students = enforce_campus_scope(students, request.user, campus_field='campus')
```

### Campus-Aware Dashboard
```python
from apps.tenant.orgsettings.campus_dashboard import get_campus_metrics

def my_dashboard(request):
    campus = get_current_campus(request)
    if campus:
        metrics = get_campus_metrics(campus)
        return render(request, 'dashboard.html', {'metrics': metrics})
```

## Troubleshooting

### Campus Mismatch Errors
If you get ValidationError about campus mismatches:
1. Check that related objects (student, offering, class_group, teacher) are in the same campus
2. Run `python manage.py check_campus_integrity` to find issues
3. Use bulk operations which handle validation automatically

### Campus Admin Can't See Data
1. Verify campus admin role is assigned: `python manage.py assign_campus_admin <username> <campus_id>`
2. Check that data has correct campus FK set
3. Ensure views use `enforce_campus_scope()` or `get_accessible_campuses()`

### Missing Campus in Dropdowns
1. Verify campus is active: `Campus.objects.filter(is_active=True)`
2. Check user has access via `get_accessible_campuses(user)`
3. For campus admins, they only see their assigned campus
