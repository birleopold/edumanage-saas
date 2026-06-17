# EduManage Mobile App Scaffold

This folder is a React Native / Expo starter for the EduManage mobile layer.

## API base

Set the tenant API base URL in `.env` or inside the app configuration:

```text
EXPO_PUBLIC_API_BASE_URL=https://your-school-domain.com/api/v1
```

## Main API endpoints

- `POST /api/v1/auth/token/` - username/password login, returns access and refresh tokens
- `POST /api/v1/auth/token/refresh/` - refresh access token
- `GET /api/v1/mobile/me/` - current user profile and roles
- `GET /api/v1/mobile/dashboard/` - role-based dashboard summary
- `GET /api/v1/mobile/students/` - student list scoped to the logged-in user
- `GET /api/v1/mobile/attendance/` - attendance summary or teacher attendance context
- `POST /api/v1/mobile/attendance/offerings/<offering_id>/mark/` - teacher attendance marking
- `GET /api/v1/mobile/finance/` - invoices, balances, payments, receipt data
- `GET /api/v1/mobile/exams/` - exam papers, attempts, published results
- `GET /api/v1/mobile/coursework/` - materials and assignments
- `GET /api/v1/mobile/messages/` - conversations and announcements
- `GET /api/v1/mobile/transport/` - transport assignments
- `POST /api/v1/mobile/devices/register/` - register push notification token
- `GET /api/v1/mobile/docs/` - tenant API documentation summary

## Install and run

```bash
cd mobile
npm install
npm run start
```

## Current scope

This is a production-ready starting scaffold, not a full polished app. It includes login token storage, API client, dashboard loading, and endpoint structure for students, parents, and teachers.
