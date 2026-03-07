# Student Performance Analytics System

## Overview

The Analytics module provides comprehensive student performance tracking, predictive analytics, and reporting capabilities. It automatically calculates GPAs, rankings, identifies at-risk students, and generates actionable insights for administrators and teachers.

## Key Features

### 📊 Performance Tracking
- **Automated GPA Calculation**: Weighted grade point averaging across all subjects
- **Class Rankings**: Automatic ranking within class and stream with percentile calculations
- **Subject Analysis**: Individual subject performance tracking with grades and rankings
- **Trend Detection**: Identifies improving, declining, or stable performance patterns

### ⚠️ Risk Assessment & Alerts
- **Predictive Analytics**: Multi-factor analysis to identify at-risk students
- **Risk Levels**: Low, Medium, High, Critical severity classifications
- **Risk Factors Tracked**:
  - Academic performance (GPA < 2.0, failing subjects)
  - Performance trends (declining grades)
  - Attendance (< 75%)
  - Discipline incidents
- **Alert Management**: Assignment, acknowledgment, and resolution tracking

### 📈 Visualizations
- **Dashboard Charts**: Performance distribution, GPA trends, risk indicators
- **Student Charts**: Grade trends over time, subject comparison graphs
- **Class Reports**: Performance distribution, subject analysis

### 👨‍🏫 Teacher Metrics
- **Effectiveness Tracking**: Based on student outcomes
- **Key Metrics**:
  - Average student scores
  - Pass rates
  - Excellence rates (students scoring ≥80%)
  - Assessment publication tracking

## Data Models

### StudentPerformanceSnapshot
Comprehensive snapshot of student performance for a specific term.

**Fields:**
- `gpa`, `overall_percentage` - Academic metrics
- `class_rank`, `stream_rank`, `percentile` - Rankings
- `performance_trend` - IMPROVING, DECLINING, STABLE
- `is_at_risk`, `risk_level`, `risk_factors` - Risk assessment
- `attendance_percentage`, `discipline_incidents` - Behavioral metrics

### SubjectPerformance
Individual subject performance details.

**Fields:**
- `assessment_average`, `exam_score`, `final_score` - Scores
- `percentage`, `grade`, `grade_point` - Grading
- `subject_rank`, `is_passed`, `is_weak_area` - Status

### ClassPerformanceReport
Aggregated class/stream statistics.

**Fields:**
- `average_gpa`, `median_gpa`, `highest_gpa`, `lowest_gpa`
- Performance distribution counts by GPA range
- `at_risk_count`, `critical_risk_count`
- `best_performing_subjects`, `worst_performing_subjects`

### AtRiskAlert
Intervention alerts for struggling students.

**Fields:**
- `severity` - LOW, MEDIUM, HIGH, CRITICAL
- `status` - OPEN, ACKNOWLEDGED, IN_PROGRESS, RESOLVED, DISMISSED
- `risk_factors` - List of identified issues
- `assigned_to`, `acknowledged_by` - Tracking
- `recommended_actions`, `resolution_notes`

## Usage Guide

### 1. Initial Setup

After installation, generate initial performance data:

```
1. Navigate to: Admin → Performance Analytics → Generate Reports
2. Select the academic term
3. Choose "All Streams" or specific stream
4. Click "Generate Snapshots"
```

This process:
- Calculates GPAs for all students
- Computes rankings and percentiles
- Identifies at-risk students
- Creates alert notifications
- Generates class performance reports

**Note**: Run this after entering exam scores and assessments for a term.

### 2. Dashboard Overview

**Access**: `/admin/analytics/`

The dashboard provides:
- **Key Metrics Cards**: Total students, average GPA, at-risk counts
- **Performance Distribution Chart**: Visual breakdown by GPA ranges
- **Recent At-Risk Alerts**: Latest intervention notifications
- **Top Performing Classes**: Highest achieving streams

### 3. Student Performance Management

**Access**: `/admin/analytics/students/`

**Features:**
- Search by name or student ID
- Filter by stream/class
- Filter by risk level (All, At Risk, Critical, High)
- Sort by rankings and GPA

**Student Detail View:**
- Overall performance metrics (GPA, rank, percentile)
- Performance trend chart (historical GPA progression)
- Subject breakdown table with grades and rankings
- Active at-risk alerts
- Historical snapshots

### 4. At-Risk Alert Management

**Access**: `/admin/analytics/alerts/`

**Workflow:**
1. **Open** - Alert created automatically
2. **Acknowledged** - Teacher acknowledges the alert
3. **In Progress** - Intervention underway
4. **Resolved** - Issue addressed successfully
5. **Dismissed** - Alert closed without action

**Actions:**
- Assign alerts to teachers
- Add resolution notes
- Track intervention timeline

### 5. Class Performance Reports

**Access**: `/admin/analytics/classes/{stream_id}/`

**Includes:**
- Overall class statistics (average GPA, highest/lowest)
- Performance distribution chart
- Top 10 performers
- At-risk students list
- Subject-wise performance table

### 6. Teacher Performance Metrics

**Access**: `/admin/analytics/teachers/`

**Metrics:**
- Average student scores by teacher
- Pass rates and excellence rates
- Assessment publication tracking
- Performance trends (improving/declining)

**Filters:**
- By academic term
- By subject/course

## Calculation Details

### GPA Calculation

```python
# Weighted by course credits
GPA = Σ(grade_point × credits) / Σ(credits)

# Final score combines assessments (40%) and exams (60%)
Final Score = (Assessment Average × 0.4) + (Exam Score × 0.6)
```

### Risk Score Algorithm

```python
risk_score = 0

# Academic factors
if GPA < 2.0: risk_score += 3
elif GPA < 2.5: risk_score += 2

# Failing subjects
risk_score += failing_subjects_count

# Trend analysis
if trend == "DECLINING": risk_score += 1

# Attendance
if attendance < 75%: risk_score += 2

# Discipline
if incidents > 2: risk_score += 1

# Classification
if risk_score >= 6: CRITICAL
elif risk_score >= 4: HIGH
elif risk_score >= 2: MEDIUM
elif risk_score > 0: LOW
```

### Ranking System

Rankings are calculated separately for:
- **Class Rank**: Position within the entire class group (all streams)
- **Stream Rank**: Position within the specific stream

Percentile = ((class_size - rank + 1) / class_size) × 100

## API Endpoints (for charts)

- `GET /admin/analytics/api/trends/{student_id}/` - Performance trend data
- `GET /admin/analytics/api/subject-performance/{student_id}/{term_id}/` - Subject chart data
- `GET /admin/analytics/api/class-performance/{stream_id}/{term_id}/` - Class distribution

## Best Practices

### When to Generate Snapshots

1. **End of Term**: After all exam results are finalized
2. **Mid-Term Updates**: When new assessments are added
3. **Before Parent Meetings**: To have latest performance data
4. **Monthly**: For early at-risk detection

### Regular Monitoring

- Review at-risk alerts **weekly**
- Check critical alerts **daily**
- Generate class reports **monthly**
- Review teacher metrics **termly**

### Intervention Workflow

1. **Identify**: System auto-generates alerts based on risk factors
2. **Assign**: Designate teacher/counselor to student
3. **Acknowledge**: Confirm alert receipt and review
4. **Act**: Implement recommended interventions
5. **Document**: Record actions taken in resolution notes
6. **Resolve**: Mark complete when student shows improvement

## Performance Considerations

### Large Student Populations

For schools with >1000 students:
- Generate snapshots **by stream** rather than all at once
- Run generation during off-peak hours
- Consider scheduled background tasks for automatic generation

### Data Retention

- Performance snapshots are retained indefinitely for trend analysis
- Old alerts (>1 year, resolved) can be archived
- Historical trends enable multi-year analysis

## Troubleshooting

### No Performance Data Showing

**Cause**: Snapshots not yet generated  
**Solution**: Run "Generate Reports" from analytics dashboard

### Rankings Not Calculated

**Cause**: Multiple snapshots needed for ranking  
**Solution**: Ensure at least 2 students have data in the same stream

### GPA Shows as N/A

**Cause**: No grading scale configured or no scores entered  
**Solution**: 
1. Check `Academics → Grading Scales` has active scale
2. Verify exam scores and assessments are entered

### Risk Alerts Not Appearing

**Cause**: Thresholds not met or attendance data missing  
**Solution**: Verify:
- GPA data is present
- Attendance sessions are recorded
- Student has performance snapshot

## Integration Points

### Required Modules

The analytics system integrates with:
- **Academics**: Course offerings, grading scales
- **Assessments**: Assessment scores
- **Exams**: Exam papers and scores
- **Attendance**: Attendance tracking
- **Discipline**: Incident records
- **Students**: Student profiles
- **Teachers**: Teacher profiles

### Data Flow

```
Assessments + Exams → Subject Scores
    ↓
GPA Calculation → Performance Snapshot
    ↓
Rankings + Risk Assessment → Alerts & Reports
```

## Future Enhancements

Possible additions:
- PDF report export for parent-teacher meetings
- Email notifications for critical alerts
- Student-facing performance dashboard
- Mobile app integration
- Machine learning predictions
- Comparative analytics across academic years
- Parent portal access to student analytics

## Support

For issues or questions:
1. Check Django logs: `python manage.py runserver` console output
2. Verify migrations: `python manage.py showmigrations analytics`
3. Check system: `python manage.py check`

## Technical Details

**Location**: `apps/tenant/analytics/`  
**Models**: `models.py` (6 models)  
**Views**: `admin_views.py` (10 views)  
**URLs**: `admin_urls.py`  
**Templates**: `templates/portals/admin/analytics/` (10 templates)  
**Utils**: `utils.py` (calculation engine)

**Dependencies**:
- Django 4.x+
- Chart.js 4.4.0 (CDN)
- Tailwind CSS (CDN)
- Alpine.js (for interactive elements)
