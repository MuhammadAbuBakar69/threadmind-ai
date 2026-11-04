# Authentication

Clerk is the identity provider. The API holds no signing key for user tokens, only the public keys
Clerk publishes.

```
browser ──sign in──▶ Clerk ──session JWT (RS256)──▶ dashboard
                                                      │  Authorization: Bearer <jwt>
                                                      ▼
                                                    API
                                        verify: iss, exp, alg=RS256, kid
                                        azp ∈ allowed origins
                                                      │  (sub, org_id)
                                                      ▼
                                   auth.resolve_identity(sub, org_id)
                                   ── SECURITY DEFINER, pinned search_path
                                                      │  (user_id, organization_id, role)
                                                      ▼
                                     set_config('app.current_org', ...)
                                     RLS enforces every row from here
```

## Configuration

| Variable | Where | Notes |
|---|---|---|
| `AUTH_PROVIDER` | API | `clerk` in any deployment holding real data. `dev` is refused when `APP_ENV=production`. |
| `CLERK_ISSUER` | API | Frontend API URL, https only. This instance: `https://fine-crane-1297.clerk.accounts.dev` |
| `CLERK_JWKS_URL` | API | Optional. Defaults to `<issuer>/.well-known/jwks.json`. |
| `CLERK_AUTHORIZED_PARTIES` | API | Comma-separated origins allowed in `azp`. Set this to the dashboard origin. |
| `CLERK_SECRET_KEY` | API | Server only. Not used for token verification, reserved for the admin API (provisioning, #20). |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | web | Public by design. The build fails loudly without it. |

`CLERK_SECRET_KEY` is not required to verify a session token. Verification needs only public keys,
which is the point of choosing an asymmetric algorithm: a compromised API host cannot mint tokens.

## What is verified, and why each check exists

| Check | Rationale |
|---|---|
| `alg` must be `RS256`, checked **before** the key is fetched | Stops `alg: none` and the classic confusion attack where an HS256 token is signed with the public key. An attacker does not get to choose the algorithm. |
| `iss` equals `CLERK_ISSUER` | A token from any other issuer is a token from an identity provider we do not trust. |
| `exp` present and in the future | Short-lived tokens are the only thing making revocation delay acceptable. |
| `kid` must exist in the JWKS | An unknown `kid` triggers exactly one refetch (key rotation is real) and then fails, so a forged `kid` cannot be used to hammer Clerk. |
| `azp` ∈ `CLERK_AUTHORIZED_PARTIES` when configured | A token minted for another property in the same Clerk application is not replayable here. |
| JWKS cached 300 s, one refetch on miss | Without a cache every request hits Clerk; without a bound on refetches, tokens are a denial-of-service lever against Clerk. |

Failure is always `401` with a generic message. The reason is withheld deliberately: telling a caller
"expired" versus "bad signature" is more useful to an attacker than to a legitimate client, and the
correlation id in the response lets an operator find the real reason in the logs.

## The role is never taken from the token

Clerk sends `org_role` (e.g. `org:admin`). It is **ignored**. The authoritative role is
`organization_members.role`, read by `auth.resolve_identity()`. A token may select which of the
caller's memberships is in play; it cannot elevate it. This is enforced by design, and
`test_the_authoritative_role_comes_from_the_database_not_the_token` fails if someone later
"optimises" it away.

## The one place RLS is bypassed

RLS is forced on `users`, `organizations` and `organization_members`, so a connection with no tenant
scope cannot read the rows needed to *establish* that scope. `auth.resolve_identity(p_provider_id,
p_clerk_org_id)` is the sanctioned bypass:

- `SECURITY DEFINER`, `search_path` pinned to `pg_catalog, public`, every identifier schema-qualified;
- `EXECUTE` revoked from `PUBLIC`, granted only to the application role;
- returns at most one row, and only when both the Clerk user id **and** the Clerk organization id
  match an active user in an active organization;
- cannot write, cannot enumerate, cannot be reached with an arbitrary org id.

Both properties are asserted in CI against real PostgreSQL
(`test_the_resolver_is_security_definer_with_a_pinned_search_path`,
`test_the_resolver_is_not_executable_by_public`), together with a test that an unscoped app-role
connection sees zero users and zero organizations without it.

## Provisioning

Clerk accounts are linked to local tenants explicitly:

```bash
python scripts/link_clerk_identity.py \
  --email owner@factory.example \
  --clerk-user-id user_2abcDEF123 \
  --clerk-org-id org_2xyzORG456 \
  --org-name "Karachi Weaving Mills" \
  --role factory_admin
```

Idempotent: re-running updates the link rather than duplicating it.

**Not yet automatic (#20).** A Clerk signup authenticates and is then refused by the membership
check. That is the safe direction to fail: no organization, no data. Auto-provisioning needs the
`organization.created` / `organizationMembership.created` webhooks verified against
`CLERK_SECRET_KEY` (Svix signature), plus a decision about whether a new signup may create a tenant
at all.

## Known gaps

| Gap | Impact | Tracked |
|---|---|---|
| No webhook provisioning | Manual onboarding per factory | #20 |
| No invitation flow from the dashboard | Admins cannot invite inspectors without the script | #20 |
| MFA policy is Clerk's default | Not enforced by our code; configure in Clerk | #20 |
| Session revocation delay | Bounded by token TTL, not instant | by design |
| Dev provider still compiled in | Reachable only when `APP_ENV != production`; refused in production | #16 (compile-time gating) |

## Dashboard wiring

`apps/web/middleware.ts` protects every route except `/`, `/sign-in`, `/sign-up`. That is a
convenience, not the authorization boundary: the API verifies every token it receives, and PostgreSQL
enforces tenancy per row, so a client that skips the middleware gains nothing.

`apps/web/lib/api.ts` takes an explicit token rather than reading one from a hook, so there is no
code path where a page renders unauthenticated data by accident.
