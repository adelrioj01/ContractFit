# ADR 0002: Establish provider-independent application identity

- Status: Accepted
- Date: 2026-10-24

## Context

The review API previously trusted organization and reviewer identifiers supplied by the browser.
That made the prototype convenient but did not establish who was acting or whether they belonged
to the organization whose data they requested. Selecting a hosted identity provider now would also
couple core authorization rules to a vendor before pilot requirements are known.

## Decision

Represent organizations, user accounts, and memberships in the application domain and database.
Passwords use Argon2 through `pwdlib`; API sessions use short-lived HS256 JWT access tokens through
PyJWT. Tokens identify the user, organization, and role, while every authenticated request reloads
the account and membership so disabled accounts or changed memberships take effect immediately.

The first protected vertical slice is the human-review API. It derives organization and reviewer
identity from the verified token and no longer accepts either value from the request body or query
string. The dashboard obtains a token through the OAuth2 password form and sends it as a Bearer
credential. Production configuration must provide a private signing secret.

## Consequences

- Authorization rules remain independent of a future Clerk, Auth0, Supabase, or OIDC integration.
- Review records cannot be read or decided by forging organization or reviewer IDs in the browser.
- The demo environment has a deterministic local reviewer account.
- Password login needs rate limiting and reset/email-verification flows before public deployment.
- Documents, jobs, profiles, opportunities, and matches must receive the same authenticated tenant
  boundary in the next hardening increment.
