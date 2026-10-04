# Google sign-in

EduManage uses one central Google OAuth callback for every school tenant.

## Google Cloud

Create one OAuth 2.0 Web application client.

Authorized JavaScript origins are not required for the server-side flow.

Register exactly this Authorized redirect URI:

    https://edumanage.leosoftug.com/auth/google/callback/

Do not register every school subdomain and do not use wildcard redirect URIs.

## Flow

1. A user starts Google sign-in from a registered tenant domain.
2. EduManage creates a cryptographically random, expiring transaction in the public schema tied to that tenant and registered return domain.
3. Google always returns to the central callback.
4. The callback validates and consumes the OAuth state, exchanges the authorization code and verifies Google's ID token.
5. EduManage creates a separate two-minute, one-use handoff token tied to the same tenant/domain.
6. The browser returns to the tenant's /auth/google/complete/ endpoint.
7. Tenant middleware selects the tenant schema; the handoff is consumed only when hostname and schema both match.
8. Google identity is matched to an existing active EduManage user. Google never grants roles or creates school membership.

OAuth state and handoff tokens are stored only as SHA-256 digests. Access and refresh tokens are not persisted.

## Environment

    GOOGLE_OAUTH_ENABLED=True
    GOOGLE_OAUTH_CLIENT_ID=<client id>
    GOOGLE_OAUTH_CLIENT_SECRET=<secret>
    GOOGLE_OAUTH_REDIRECT_URI=https://edumanage.leosoftug.com/auth/google/callback/
    GOOGLE_OAUTH_TRANSACTION_MINUTES=10
    GOOGLE_OAUTH_HANDOFF_MINUTES=2

Password login remains available.
