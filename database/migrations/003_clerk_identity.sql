-- ===========================================================================
-- 003 — Clerk as the identity provider
--
-- Until now tokens were self-signed with a shared JWT_SECRET (SEC-002), which means anyone holding
-- that secret could mint a super_admin token for any factory. With Clerk, tokens are signed by
-- Clerk with a private key we never see, and verified against Clerk's published JWKS.
--
-- Two identity columns make the mapping explicit:
--   * users.authentication_provider_id already existed for exactly this purpose.
--   * organizations.clerk_org_id links a Clerk organization to a local tenant.
--
-- The role is NOT taken from the token. Clerk's org_role is a label in Clerk's domain; the
-- authoritative role is organization_members.role in our database. A token can therefore select
-- which of the caller's memberships is in play, but never elevate it.
-- ===========================================================================

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS clerk_org_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS authentication_provider_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_clerk_org_id
    ON organizations (clerk_org_id) WHERE clerk_org_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_provider_id
    ON users (authentication_provider_id) WHERE authentication_provider_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Identity resolution.
--
-- Chicken and egg: RLS is forced on users, organizations and organization_members, so a connection
-- with no scope set cannot read the very rows needed to establish that scope. A SECURITY DEFINER
-- function is the controlled bypass, and it is deliberately narrow:
--
--   * one query, one row, four columns;
--   * search_path pinned to pg_catalog, public so a caller cannot shadow a table name;
--   * every identifier schema-qualified;
--   * EXECUTE revoked from PUBLIC and granted only to the application role;
--   * it cannot write, and it cannot enumerate: a caller must already know both the Clerk user id
--     and the Clerk organization id to get a row back.
--
-- This is the only place in the schema where RLS is intentionally stepped around, which is why it
-- lives in its own schema with its own comment.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.resolve_identity(p_provider_id TEXT, p_clerk_org_id TEXT)
RETURNS TABLE (user_id UUID, organization_id UUID, role TEXT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT u.id, m.organization_id, m.role
    FROM public.users u
    JOIN public.organization_members m ON m.user_id = u.id
    JOIN public.organizations o ON o.id = m.organization_id
    WHERE u.authentication_provider_id = p_provider_id
      AND u.status = 'active'
      AND o.status = 'active'
      AND o.clerk_org_id = p_clerk_org_id
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION auth.resolve_identity(TEXT, TEXT) FROM PUBLIC;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'threadmind_app') THEN
    -- USAGE on the schema is required as well: EXECUTE alone leaves the function unreachable.
    EXECUTE 'GRANT USAGE ON SCHEMA auth TO threadmind_app';
    EXECUTE 'GRANT EXECUTE ON FUNCTION auth.resolve_identity(TEXT, TEXT) TO threadmind_app';
  END IF;
END $$;

COMMENT ON FUNCTION auth.resolve_identity(TEXT, TEXT) IS
    'Maps a verified Clerk identity to a local (user, organization, role). SECURITY DEFINER with a '
    'pinned search_path; the only sanctioned bypass of RLS in the schema.';
