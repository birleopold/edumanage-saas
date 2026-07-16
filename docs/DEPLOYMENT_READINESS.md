# EduManage deployment readiness checklist

This checklist should be completed before onboarding real school clients.

## Recommended priority order

1. **Production PostgreSQL tenant setup**
   - Use `config.settings.tenants` in production.
   - Configure `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT`.
   - Run shared/public migrations first.
   - Run tenant migrations for every tenant schema.
   - Confirm active tenants have schemas before giving users access.

2. **Environment variables**
   - Set `DJANGO_SECRET_KEY` to a strong private value.
   - Set `DJANGO_DEBUG=False`.
   - Set `DJANGO_ALLOWED_HOSTS` to real platform/custom domains only.
   - Configure database, email, SMS, webhook, and web-push variables.
   - Never commit live credentials to Git.

3. **Domain routing**
   - Point the main platform domain to the app server or load balancer.
   - Configure wildcard/subdomain routing for school subdomains.
   - Test custom-domain DNS instructions.
   - Verify that unknown/invalid domains show the friendly invalid-domain page.

4. **SSL certificates**
   - Enforce HTTPS at the proxy or load balancer.
   - Install the main platform certificate.
   - Prepare wildcard or automated per-domain certificate flow.
   - Track SSL status on tenant domain records.
   - Monitor certificate renewal.

5. **Package/subscription go-live checks**
   - Confirm Starter, Standard, Enterprise and Custom plans are present.
   - Confirm every tenant has a subscription record.
   - Test trial status, active status, past-due status and suspended status.
   - Test invoice creation and payment recording.
   - Confirm suspended subscriptions pause tenant access while preserving data.

6. **Backups and restore drills**
   - Schedule nightly PostgreSQL backups.
   - Store encrypted backups off-server.
   - Keep tenant export/backup tools available to schools.
   - Test restore on a separate environment.
   - Document backup retention and restore responsibility.

7. **Admin security**
   - Keep the Platform Console restricted to trusted superusers.
   - Enable admin 2FA policy in production.
   - Remove demo/default accounts.
   - Enforce first-login password change for school-owner accounts.
   - Confirm audit/activity tracking is visible.

8. **Monitoring and uptime checks**
   - Monitor `/health/` externally.
   - Monitor CPU, memory, disk, database size, and response time.
   - Add disk-space alerts for media and backups.
   - Define support escalation/on-call contact.

9. **Error logging and provider setup**
   - Keep friendly error pages for users.
   - Capture server-side stack traces in logs or an error tracking tool.
   - Configure SMTP provider and sender email.
   - Configure SMS gateway URL/token/sender ID.
   - Avoid logging sensitive student/finance data.

10. **Final go-live rehearsal**
    - Create a test tenant through the Platform Console.
    - Add school-owner admin and complete first login.
    - Verify domain, SSL status, subscription, exports, reports, audit logs, and PWA install.
    - Run backup and restore test.
    - Sign off before real clients are onboarded.

## Important production commands

```bash
python manage.py check_operational_readiness --strict
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant
python manage.py collectstatic --noinput
python manage.py check --deploy
```

For production-settings verification, run the command with the production settings module:

```bash
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check_operational_readiness --strict --require-production-settings
```

## Suggested environment variables

See `.env.production.example` for a production-oriented template.
