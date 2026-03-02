# Grading System & Class Streams Implementation

## Overview
This document outlines the implementation of critical missing features for school management:
1. **Grading Scale System** - Convert numeric scores to letter grades
2. **Class Streams** - Divide classes into sections (A, B, C)
3. **Report Card Generation** - Automated student report cards
4. **Student Rankings** - Class position calculations

## What Was Implemented

### 1. Grading Scale System

#### Models Added (`apps/tenant/academics/models.py`)
- **GradingScale**: Define grading systems (e.g., "Primary Scale", "IGCSE Scale")
  - `name`: Scale name
  - `description`: Optional description
  - `is_default`: Mark as default scale
  - `is_active`: Enable/disable scale

- **GradeRange**: Define grade boundaries within a scale
  - `scale`: Foreign key to GradingScale
  - `grade`: Letter grade (A, B+, etc.)
  - `min_score`: Minimum percentage
  - `max_score`: Maximum percentage
  - `grade_point`: GPA value (optional)
  - `remark`: Description (Excellent, Good, etc.)
  - `order`: Display order

**Example Usage:**
```python
# Create a grading scale
scale = GradingScale.objects.create(
    name="Standard Scale",
    is_default=True
)

# Add grade ranges
GradeRange.objects.create(scale=scale, grade="A", min_score=80, max_score=100, grade_point=4.0, remark="Excellent")
GradeRange.objects.create(scale=scale, grade="B", min_score=70, max_score=79, grade_point=3.0, remark="Very Good")
GradeRange.objects.create(scale=scale, grade="C", min_score=60, max_score=69, grade_point=2.0, remark="Good")
```

### 2. Class Streams

#### Model Added (`apps/tenant/academics/models.py`)
- **Stream**: Class divisions/sections
  - `class_group`: Foreign key to ClassGroup
  - `name`: Stream name (A, B, C, East, West, etc.)
  - `capacity`: Maximum students (default 40)
  - `class_teacher`: Assigned teacher
  - `room`: Classroom location
  - `is_active`: Enable/disable

#### Student Model Updated (`apps/tenant/students/models.py`)
- Added `stream` field to StudentProfile
- Links students to specific class streams

**Example Usage:**
```python
# Create streams for Form 1
form1 = ClassGroup.objects.get(name="Form 1")
Stream.objects.create(class_group=form1, name="A", capacity=40, room="Room 101")
Stream.objects.create(class_group=form1, name="B", capacity=40, room="Room 102")

# Assign student to stream
student.stream = Stream.objects.get(class_group__name="Form 1", name="A")
student.save()
```

### 3. Grade Calculation Utilities (`apps/tenant/academics/grading.py`)

Functions implemented:
- `get_letter_grade(score, grading_scale)` - Convert score to letter grade
- `calculate_weighted_average(student_id, offering_id)` - Calculate course average
- `calculate_term_average(student_id, term_id)` - Calculate overall term average
- `calculate_gpa(student_id, term_id, grading_scale)` - Calculate GPA
- `get_class_rank(student_id, term_id, stream_id)` - Get student ranking
- `get_subject_statistics(offering_id)` - Get subject performance stats

### 4. Report Card System (`apps/tenant/academics/reports.py`)

#### ReportCard Class
Generates comprehensive student report cards with:
- Student information (name, ID, stream, campus)
- Term information
- Subject-by-subject results with grades
- Overall summary (average, highest, lowest)
- Class ranking and percentile

**Usage:**
```python
from apps.tenant.academics.reports import ReportCard

# Generate report card
report = ReportCard(student_id=1, term_id=1)
data = report.to_dict()

# Access data
print(data['summary']['average'])  # Overall average
print(data['ranking']['rank'])     # Class position
print(data['subjects'])            # List of subject results
```

#### Helper Functions
- `generate_class_report_cards(term_id, stream_id, class_group_id)` - Bulk generation
- `get_term_statistics(term_id, stream_id)` - Term-wide statistics

### 5. Admin Views Added (`apps/tenant/academics/views.py`)

**Grading Scales:**
- `grading_scale_list` - List all grading scales
- `grading_scale_create` - Create new scale
- `grading_scale_edit` - Edit existing scale
- `grading_scale_detail` - View scale with grade ranges
- `grade_range_create` - Add grade range to scale
- `grade_range_edit` - Edit grade range

**Streams:**
- `stream_list` - List all streams
- `stream_create` - Create new stream
- `stream_edit` - Edit existing stream

**Report Cards:**
- `report_card_view` - View individual student report card
- `term_report_cards` - Generate bulk report cards for a term/stream/class

### 6. Forms Added (`apps/tenant/academics/forms.py`)
- `GradingScaleForm` - Create/edit grading scales
- `GradeRangeForm` - Create/edit grade ranges
- `StreamForm` - Create/edit streams

### 7. URL Routes Added (`apps/tenant/academics/urls.py`)
```
/admin/academics/grading-scales/
/admin/academics/grading-scales/create/
/admin/academics/grading-scales/<id>/
/admin/academics/grading-scales/<id>/edit/
/admin/academics/grading-scales/<scale_id>/ranges/create/
/admin/academics/grade-ranges/<id>/edit/

/admin/academics/streams/
/admin/academics/streams/create/
/admin/academics/streams/<id>/edit/

/admin/academics/report-cards/<student_id>/<term_id>/
/admin/academics/terms/<term_id>/report-cards/
```

## Next Steps Required

### 1. Create Database Migrations
```bash
python manage.py makemigrations academics students
python manage.py migrate
```

### 2. Create Admin Templates
You need to create these templates in `templates/portals/admin/academics/`:
- `grading_scales_list.html` - List grading scales
- `grading_scale_detail.html` - View scale with grade ranges
- `streams_list.html` - List streams
- `report_card.html` - Individual report card view
- `term_report_cards.html` - Bulk report cards view

### 3. Update Admin Sidebar
Add menu items for:
- Grading Scales (under Academics section)
- Streams (under Academics section)
- Report Cards (under Academics section)

### 4. Seed Initial Data
Create a default grading scale:
```python
# In Django shell or data migration
scale = GradingScale.objects.create(name="Standard Grading Scale", is_default=True)
GradeRange.objects.bulk_create([
    GradeRange(scale=scale, grade="A", min_score=80, max_score=100, grade_point=4.0, remark="Excellent", order=1),
    GradeRange(scale=scale, grade="B", min_score=70, max_score=79, grade_point=3.0, remark="Very Good", order=2),
    GradeRange(scale=scale, grade="C", min_score=60, max_score=69, grade_point=2.0, remark="Good", order=3),
    GradeRange(scale=scale, grade="D", min_score=50, max_score=59, grade_point=1.0, remark="Pass", order=4),
    GradeRange(scale=scale, grade="F", min_score=0, max_score=49, grade_point=0.0, remark="Fail", order=5),
])
```

## Usage Workflow

### Setting Up Grading
1. Admin creates grading scale(s)
2. Admin adds grade ranges to each scale
3. Admin sets one scale as default

### Setting Up Streams
1. Admin creates class groups (already exists)
2. Admin creates streams for each class group
3. Admin assigns students to streams

### Generating Report Cards
1. Teachers enter assessment scores (already exists)
2. Teachers enter exam scores (already exists)
3. Admin generates report cards for a term
4. System calculates:
   - Subject averages
   - Letter grades
   - Overall average
   - Class rankings
   - Percentiles

### Viewing Reports
- Individual: `/admin/academics/report-cards/<student_id>/<term_id>/`
- Bulk: `/admin/academics/terms/<term_id>/report-cards/?stream=<stream_id>`

## Benefits

1. **Professional Report Cards** - Automated generation with grades, rankings, and statistics
2. **Flexible Grading** - Support multiple grading scales for different programs
3. **Better Organization** - Streams allow proper class management for large schools
4. **Performance Tracking** - Rankings and statistics help identify top performers
5. **Time Savings** - Automated calculations eliminate manual work
6. **Data-Driven Decisions** - Statistics help improve teaching and curriculum

## Technical Notes

- All grade calculations use `Decimal` for precision
- Rankings are calculated per stream (if assigned) or across all students
- Report cards cache calculations for performance
- Grading scales support GPA calculation (optional)
- System handles missing scores gracefully
- Supports both term and semester systems

## Future Enhancements

Consider adding:
1. PDF export for report cards
2. Email report cards to parents
3. Progress reports (mid-term)
4. Teacher comment banks
5. Subject-specific grading scales
6. Grade trend analysis
7. Bulk student stream assignment
8. Automatic stream balancing (distribute students evenly)
