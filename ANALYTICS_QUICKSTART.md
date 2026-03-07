# Analytics System - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Generate Initial Data (2 minutes)

1. Log in as an administrator
2. Navigate to: **Admin Portal → Performance Analytics**
3. Click **"Generate Reports"** button (top right)
4. Select the current academic term from dropdown
5. Leave "All Streams" selected (or pick specific stream)
6. Click **"Generate Snapshots"**

⏱️ **Wait 1-2 minutes** for processing (depends on student count)

✅ You should see success message: "Successfully generated X performance snapshots"

### Step 2: View Dashboard (30 seconds)

Navigate back to **Performance Analytics** dashboard to see:

📊 **5 Key Metrics Cards:**
- Total Students
- Average GPA
- Excellent Students (GPA ≥ 3.5)
- At-Risk Students
- Critical Risk Count

📈 **Visual Charts:**
- Performance Distribution (doughnut chart)
- GPA Distribution (bar chart)

### Step 3: Check At-Risk Students (1 minute)

1. Click **"At-Risk Alerts"** from Quick Actions
2. Review list of students requiring intervention
3. Click any alert to see:
   - Risk factors identified
   - Recommended actions
   - Student details

**Take Action:**
- Click **"Acknowledge"** to confirm review
- Assign alert to a teacher
- Add resolution notes as you work with student

### Step 4: View Individual Student (1 minute)

1. Go to **"Student Performance"** section
2. Search for a student by name
3. Click **"View Details"**

You'll see:
- 📊 Performance trend chart (GPA over time)
- 📈 Subject performance chart
- 📋 Detailed subject breakdown table
- ⚠️ Active alerts (if any)

### Step 5: Review Class Performance (30 seconds)

1. From dashboard, click any class in **"Top Performing Classes"**
2. View comprehensive class report with:
   - Class statistics
   - Performance distribution chart
   - Top 10 students
   - At-risk students
   - Subject-wise performance

---

## 📋 Common Tasks

### Generate Reports After New Exam Results

```
Admin → Performance Analytics → Generate Reports
→ Select Term → Generate Snapshots
```

**When to do this:**
- After entering exam scores
- After publishing new assessments
- Monthly for updated rankings

### Monitor At-Risk Students

```
Admin → Performance Analytics → At-Risk Alerts
→ Filter by: Critical/High
→ Review and assign to teachers
```

**Best Practice:** Check daily for critical alerts, weekly for all alerts

### Export Student Report for Parent Meeting

```
Admin → Performance Analytics → Student Performance
→ Find student → View Details
→ (Use browser print function: Ctrl+P)
```

### View Teacher Effectiveness

```
Admin → Performance Analytics → Teacher Metrics
→ Filter by subject/term
→ Review pass rates and scores
```

---

## 🎯 Understanding the Metrics

### GPA Scale
- **4.0**: Perfect (A grade, 90-100%)
- **3.5-3.9**: Excellent (A- to B+)
- **3.0-3.4**: Good (B range)
- **2.5-2.9**: Average (C+ to B-)
- **2.0-2.4**: Below Average (C range)
- **< 2.0**: Failing (need intervention)

### Risk Levels
- **🟢 Low**: Minor concerns, monitor
- **🟡 Medium**: Multiple factors, intervene
- **🟠 High**: Serious concerns, immediate action
- **🔴 Critical**: Urgent intervention required

### Percentile
- **90th percentile**: Top 10% of class
- **75th percentile**: Top 25% of class
- **50th percentile**: Middle of class
- **25th percentile**: Bottom 25% of class

---

## ⚡ Pro Tips

### 1. Set Up Regular Snapshots
Generate snapshots at consistent intervals (end of each month) to track trends accurately.

### 2. Use Filters Effectively
When viewing student performance list:
- Filter by "At Risk" to focus on interventions
- Filter by stream for class-specific analysis
- Use search for quick student lookup

### 3. Monitor Trends, Not Just Snapshots
A student with declining trend (even if GPA is okay) needs attention before becoming at-risk.

### 4. Assign Alerts Promptly
Assign at-risk alerts to class teachers or counselors immediately for faster intervention.

### 5. Document Interventions
Always add resolution notes to alerts - this creates a record of interventions tried.

---

## 🔧 Troubleshooting

### "No data available"
**Fix:** Generate snapshots first (Step 1 above)

### Rankings show as "—"
**Fix:** Need at least 2 students with data in same stream. Re-run snapshot generation.

### GPA shows "N/A"
**Fix:** 
1. Check if grading scale is configured (Admin → Academics → Grading Scales)
2. Ensure exam scores are entered for the student

### Charts not displaying
**Fix:** 
1. Check browser console for errors
2. Ensure internet connection (Chart.js loads from CDN)
3. Try refreshing the page

---

## 📊 Recommended Workflow

### Weekly Routine
1. ✅ Monday: Review new at-risk alerts
2. ✅ Wednesday: Check student performance list for trends
3. ✅ Friday: Update alert resolutions

### Monthly Routine
1. ✅ First week: Generate new performance snapshots
2. ✅ Mid-month: Review class performance reports
3. ✅ End-month: Analyze teacher metrics

### Term-End Routine
1. ✅ Generate final snapshots
2. ✅ Create class performance reports
3. ✅ Prepare student reports for parent meetings
4. ✅ Review teacher effectiveness metrics
5. ✅ Identify students needing summer support

---

## 🎓 Next Steps

Once comfortable with basics:
1. Explore **subject-wise performance** in class reports
2. Use **teacher metrics** for professional development planning
3. Track **historical trends** across multiple terms
4. Develop **intervention strategies** based on risk factors

## 📞 Need Help?

- Check `apps/tenant/analytics/README.md` for detailed documentation
- Run `python manage.py check` to verify system integrity
- Review Django logs for any errors

---

**💡 Remember**: The analytics system is a tool to support student success. Use insights to provide timely interventions and celebrate improvements!
