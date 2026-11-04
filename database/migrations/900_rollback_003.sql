-- Rollback for 003_clerk_identity.sql.
--
-- Drops the resolver, the indexes and the columns. Removing the columns also removes the Clerk
-- mapping, so any deployment that rolls this back stops authenticating Clerk tokens entirely: the
-- API must be switched back to the dev provider in the same change.

DROP FUNCTION IF EXISTS auth.resolve_identity(TEXT, TEXT);
DROP SCHEMA IF EXISTS auth;

DROP INDEX IF EXISTS uq_users_provider_id;
DROP INDEX IF EXISTS uq_organizations_clerk_org_id;

ALTER TABLE organizations DROP COLUMN IF EXISTS clerk_org_id;
