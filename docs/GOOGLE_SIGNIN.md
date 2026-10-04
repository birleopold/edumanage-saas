# Google sign-in

EduManage supports Google as a federated identity provider for existing school accounts.

## Security model

Google proves identity only. EduManage remains authoritative for the tenant, user record, roles, campus scope, account status and permissions. A Google identity never creates or grants a school role.

A first Google sign-in is accepted only when Google supplies a verified email and exactly one active user in the current tenant has that email. The Google immutable subject identifier is then stored in that tenant schema. Future sign-ins use the subject link.

No Google access token or refresh token is persisted because EduManage does not need access to Google APIs for authentication.

Password login remains available as a recovery/fallback path.

## Google Cloud configuration

Create an OAuth 2.0 Web application client and register the callback URL for each school domain that will use Google sign-in:

    https://<school-domain>/auth/google/callback/

Set these only in the server environment:

    GOOGLE_OAUTH_ENABLED=True
    GOOGLE_OAUTH_CLIENT_ID=<client id>
    GOOGLE_OAUTH_CLIENT_SECRET=<client secret>

Never commit the client secret.

Because Google requires exact redirect URI matching, every production tenant hostname used for OAuth must be registered with the Google OAuth client. If operating many arbitrary custom domains, use a dedicated central identity domain/proxy in a later architecture rather than trying to register unbounded redirects.

## Account creation policy

Google does not create students, parents, teachers or administrators. School accounts must be provisioned by EduManage first. This prevents a personal Google account from self-assigning a role or entering the wrong school.
