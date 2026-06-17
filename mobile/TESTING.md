# EduManage Mobile Testing

## Android

- Open the app.
- Confirm the tenant API connection.
- Confirm dashboard data loads for parent, student, and teacher accounts.
- Confirm teacher attendance marking works.
- Confirm finance, coursework, exams, messages, and transport screens load.
- Confirm notification permission prompt appears.
- Confirm the device record appears in Django admin.

## iOS

- Open the app on a real device.
- Confirm the tenant API connection.
- Confirm role-based dashboard data loads.
- Confirm mobile layout fits small screens.
- Confirm notification permission prompt appears.

## Tenant checks

- Test one school domain at a time.
- Confirm a parent sees only linked children.
- Confirm a student sees only personal data.
- Confirm a teacher sees only assigned classes.
- Test using HTTPS.

## Release checks

- Run backend migrations.
- Run API smoke tests.
- Build Android and iOS release packages after successful testing.
