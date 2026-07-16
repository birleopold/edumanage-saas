# Monitoring plan

Configure external uptime monitoring before production onboarding. The monitor should run from outside the hosting network so DNS, TLS, routing, and application availability are all exercised.

## Public probes

| Probe | Method | Expected | Frequency | Alert after |
| --- | --- | --- | --- | --- |
| `/health/` | `GET` | HTTP 200 JSON with `status: "ok"` | 1 minute | 2 consecutive failures |
| `/status/?format=json` | `GET` | HTTP 200 JSON with `ok: true` and `status: "ok"` | 5 minutes | 2 consecutive failures |

The `/health/` route is the minimal load-balancer/uptime probe. The `/status/?format=json` route is the public status probe for tenant-facing application health. Neither response exposes secrets or personal data.

## Infrastructure alerts

Configure host or provider alerts for:

- CPU saturation over 85% for 10 minutes.
- Memory pressure or swap activity sustained for 10 minutes.
- Disk usage over 80%, with separate alerts for media and backup volumes.
- Database storage over 80%.
- Database connection exhaustion or repeated connection failures.
- TLS certificate expiry inside 14 days.

## Ownership

- Primary responder: platform operations owner.
- Escalation: engineering owner for application errors, hosting provider for network/database incidents, payment or messaging provider support for integration outages.
- During an incident, update the public status page or external status vendor when user-facing availability is affected.
