"""Tenant resolution.

The single most important rule in this package: an `organization_id` that arrives from a client
is a *claim*, never an authorization. It is resolved against the caller's memberships, and the
transaction is scoped with `SET LOCAL app.current_org` so that PostgreSQL row-level security
enforces isolation even if a query forgets a WHERE clause.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

ROLE_RANK = {
    "quality_inspector": 10,
    "production_supervisor": 20,
    "maintenance_engineer": 20,
    "factory_manager": 30,
    "factory_admin": 40,
    "super_admin": 100,
}


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    organization_id: UUID
    role: str

    def at_least(self, role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]


class NotAMember(Exception):
    """Raised when a claimed organization does not match any membership for the caller."""


def resolve_principal(db: Session, user_id: UUID, claimed_org: UUID) -> Principal:
    row = db.execute(
        text(
            """
            SELECT organization_id, role
            FROM organization_members
            WHERE user_id = :user_id AND organization_id = :org_id
            """
        ),
        {"user_id": user_id, "org_id": claimed_org},
    ).first()

    if row is None:
        raise NotAMember(str(claimed_org))

    return Principal(user_id=user_id, organization_id=row[0], role=row[1])


def scope_session(db: Session, principal: Principal) -> None:
    """Bind the transaction to one organization. Call immediately after resolving the principal."""
    db.execute(text("SET LOCAL app.current_org = :org"), {"org": str(principal.organization_id)})
