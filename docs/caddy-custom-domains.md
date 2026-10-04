# Caddy custom-domain TLS handoff

EduManage uses Caddy as the public TLS edge and keeps Nginx as an internal static/media/Gunicorn proxy.

## Architecture

Internet -> Caddy :80/:443 -> Nginx 127.0.0.1:8080 -> Gunicorn unix socket

Caddy On-Demand TLS is restricted by:

    http://127.0.0.1:8080/_internal/caddy/allow-domain?domain=<hostname>

The endpoint returns 200 only when the hostname exists in the public-schema Domain table and its tenant is active. Unknown and suspended domains return 404. It performs only an indexed database lookup.

## One-time VPS installation

Do not run this blindly on an unrelated host. Back up current Nginx configuration first.

1. Deploy current EduManage main and run shared migrations.
2. Set a real ACME contact email in /etc/caddy/edumanage.env:

       CADDY_ACME_EMAIL=admin@leosoftug.com

3. Install Caddy from its official Ubuntu repository.
4. Copy ops/nginx-edumanage-internal.conf to /etc/nginx/sites-available/edumanage-internal and enable it.
5. Disable the old public EduManage Nginx server block so Nginx no longer owns :80/:443 for EduManage.
6. Copy ops/Caddyfile to /etc/caddy/Caddyfile.
7. Validate both configurations before restart:

       sudo nginx -t
       sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

8. Restart Nginx, then Caddy.
9. Confirm Caddy owns public :80/:443 and Nginx only listens on 127.0.0.1:8080 for EduManage.
10. Test the main platform, a managed school subdomain, and one client-owned custom domain.

## Staff workflow after handoff

Platform staff add the client-owned hostname in /platform/, give the customer the displayed DNS values, and click Check DNS & HTTPS after propagation. No SSH, Nginx edit, Certbot command or Caddy reload is required for subsequent domains.

Caddy requests a certificate only after the hostname is registered to an active EduManage tenant. Certificate renewal is automatic.
