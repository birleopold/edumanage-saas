# Platform Admin Console

This module exposes public-schema SaaS tenant and domain management outside raw Django admin.

## Access

- URL: `/platform/`
- Login: `/platform/login/`
- Logout: `/platform/logout/`
- Access is restricted to authenticated Django superusers only.

## Non-technical tenant onboarding

The simplest intended workflow is:

1. Buy the client's domain name.
2. Point the domain DNS to the EduManage server, proxy, or load balancer.
3. Open `/platform/tenants/create/`.
4. Enter the school name, schema name, status, and client domain name.
5. Submit the form.

The tenant and its primary custom domain are created together. The platform owner does not need to open Django admin or add the domain on a second screen.

## Included in the first rollout

- Platform dashboard with tenant/domain counts.
- Tenant list with search, status filter and pagination.
- Tenant creation and editing.
- Tenant creation with automatic primary custom domain attachment.
- Tenant status updates.
- Tenant detail page with schema readiness check.
- Domain creation and editing.
- Primary domain selection.
- Manual domain verification.
- Domain deletion.
- Tenant status middleware for unavailable tenant portals.
- Safer platform login redirect handling.
- Focused middleware and redirect safety tests.

## Notes

- Schema existence checks are available when running in PostgreSQL tenant mode.
- Tenant schema names are locked after creation to protect tenant data.
- Domain verification is manual in this version. A future version can automate verification using DNS records.
- The public schema remains available so platform superusers can manage tenant status from `/platform/`.
- DNS and SSL should be handled at hosting/proxy level, for example through Cloudflare, Caddy, Traefik, Nginx plus certificates, or a managed load balancer.

## Suggested verification before merge

Run Django checks and the public tenant tests using tenant settings, then smoke-test platform routes and tenant availability behavior in a tenant-aware PostgreSQL environment. Local execution was not performed in the ChatGPT tool environment.


## Client-owned / already registered domains

Platform staff do not need SSH or VPS access to onboard a school that already owns a domain.

1. Open the school in Platform Console and add the hostname the school wants to use.
2. For a root/apex domain, give the domain administrator the A-record target displayed by EduManage. For a portal/www subdomain, prefer the displayed CNAME target.
3. The domain administrator makes the change at their registrar/DNS provider (for example Cloudflare, cPanel, GoDaddy or their local registrar). They should remove conflicting A/AAAA/CNAME records for the same hostname.
4. Wait for public DNS propagation, then click **Check DNS & HTTPS** in EduManage.
5. EduManage resolves the hostname and only marks DNS verified when it points to the configured EduManage origin. It also performs an HTTPS request and reports SSL active only when a valid certificate is being served.
6. Do not hand over the custom-domain login URL until both DNS and HTTPS are green.

The application does not require staff to edit Nginx or log into the VPS. Production infrastructure must provide automatic TLS for registered custom domains. For a dynamic SaaS domain fleet, use a reverse proxy/TLS layer capable of on-demand certificate issuance restricted by an allow/ask endpoint backed by the EduManage Domain table. Never enable unrestricted on-demand certificate issuance.
