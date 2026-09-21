# API exposure matrix

This is the security contract for HTTP APIs. New routes must declare the same
exposure class in code and tests before release.

| Surface | Exposure | Required control |
| --- | --- | --- |
| `/api/v1/whoami/` | Public tenant metadata | Throttled; no personal or secret data |
| `/api/v1/mobile/docs/`, `/api/v1/mobile/openapi/` | Public documentation | Throttled; schema only |
| `/api/v1/auth/token/*` | Public credential exchange | Anonymous throttling and normal authentication validation |
| `/api/v1/mobile/*` | Tenant user | JWT/session authentication plus endpoint role/relationship checks |
| `/api/v1/mobile/teachers/` | Teacher or school administrator | Explicit role permission; no student/parent access |
| `/api/v1/mobile/attendance/*/mark/` | Assigned teacher or school administrator | Role permission, offering ownership, validated atomic payload |
| `/api/v1/integrations/health/` | Integration key | `health-read` or `integrations-admin` scope |
| `/api/v1/integrations/message-logs/` | Integration key | `messages-read` or `integrations-admin`; PII masked |
| `/api/v1/integrations/webhook-deliveries/` | Integration key | `webhooks-read` or `integrations-admin`; error details withheld |
| `/api/v1/integrations/callbacks/*` | Provider callback | Provider signature/secret verification and throttling |
| `/api/v1/attendance/devices/*` | Device integration | Device credentials, replay/idempotency checks, tenant isolation |
| Platform console/admin routes | Platform staff | Platform authorization and configured step-up verification |

The mobile API must obtain records through the authenticated user's student,
parent, teacher, campus, or administrative scope. Authentication alone is not
authorization to tenant-wide directories.
