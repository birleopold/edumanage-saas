# Student Risk Radar

Student Risk Radar is an admin early-warning dashboard that combines live school signals into one action list.

## Where To Find It

- Admin page: `/admin/analytics/risk-radar/`
- Analytics dashboard: `/admin/analytics/`
- Admin sidebar: Risk Radar
- Admin home: Student Risk Radar card

## Signals Used

The radar checks active students and scores each student when one or more warning signals exists:

- Attendance below 75 percent in the last 14 days
- Attendance decline of 15 percentage points or more versus the prior 14 days
- Active invoice balance above zero
- Recent assessment average below 50 percent
- Recent discipline incidents that are not dismissed
- Overdue coursework without a submitted response

## Risk Levels

- `CRITICAL`: score 9 or above
- `HIGH`: score 6 to 8
- `MEDIUM`: score 3 to 5
- `LOW`: score 1 to 2

The page links each row back to the existing student analytics detail page.

## Operational Notes

- No new database table or migration is required.
- The radar is calculated from existing attendance, finance, assessment, discipline and coursework records.
- It is intentionally conservative: students with no current signals are omitted from the list.
