"""Shared dependencies.

Route handlers receive a `Principal` and a scoped session; they never parse tokens, and they never
read an organization id out of a request body.
"""

from __future__ import annotations

from collections.abc import Iterator

from core.auth import decode_token
from core.clerk import verify_clerk_token
from core.config import get_settings
from core.errors import Forbidden, Unauthenticated
from core.identity import resolve_principal as resolve_provider_principal
from core.security import Principal, scope_session
from db import get_sessionmaker
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise Unauthenticated("A bearer token is required.")

    settings = get_settings()
    if not settings.uses_clerk:
        return decode_token(credentials.credentials)

    identity = verify_clerk_token(
        credentials.credentials,
        issuer=settings.clerk_issuer,
        jwks=settings.clerk_jwks_url or None,
        authorized_parties=settings.authorized_parties,
    )

    # Identity resolution needs a session, and it needs one *before* any tenant scope exists:
    # the scope is what we are trying to establish. The session is short-lived and intentionally
    # unscoped - it only ever calls auth.resolve_identity(), which returns one row it was asked
    # for by exact provider id.
    session: Session = get_sessionmaker()()
    try:
        return resolve_provider_principal(
            session,
            provider_user_id=identity.provider_user_id,
            provider_org_id=identity.provider_org_id,
        )
    finally:
        session.close()


def require_role(role: str):
    """Dependency factory. Raises 403 unless the caller's role ranks at or above `role`."""

    def _dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.at_least(role):
            raise Forbidden(f"This action requires the {role} role.")
        return principal

    return _dependency


def get_tenant_db(principal: Principal = Depends(get_principal)) -> Iterator[Session]:
    """A session already scoped to the caller's organization.

    The scope is applied inside the transaction, before the handler runs, so RLS is active for
    every statement the handler issues. There is no path to an unscoped session through this
    dependency, which is the point.
    """
    session: Session = get_sessionmaker()()
    try:
        scope_session(session, principal)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
