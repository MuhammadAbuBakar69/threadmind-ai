"""Mapping a verified identity-provider account to a local tenant identity.

The provider answers "who is this". It does not answer "which tenant, with which role" — that is
our data, and it is the only place authority comes from. The lookup goes through
`auth.resolve_identity()`, a narrow SECURITY DEFINER function that is the single sanctioned bypass
of row-level security in the schema (see 003_clerk_identity.sql).

No membership means no access. It does not fall back to a default organization, because a silent
default is how a user with no membership ends up reading another factory's data.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.errors import Forbidden
from core.security import Principal

RESOLVE_STATEMENT = text(
    "SELECT user_id, organization_id, role FROM auth.resolve_identity(:provider_id, :provider_org)"
)


def resolve_principal(
    db: Session, *, provider_user_id: str, provider_org_id: str | None
) -> Principal:
    if not provider_org_id:
        # An organization must be selected before the API can serve tenant data. Returning 403
        # rather than 401 is deliberate: the credentials are fine, the account is not set up.
        raise Forbidden("Select an organization before using this workspace.")

    row = db.execute(
        RESOLVE_STATEMENT,
        {"provider_id": provider_user_id, "provider_org": provider_org_id},
    ).first()

    if row is None:
        raise Forbidden("This account is not a member of the requested organization.")

    return Principal(user_id=row[0], organization_id=row[1], role=row[2])
