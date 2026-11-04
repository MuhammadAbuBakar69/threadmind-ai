"""Token authentication.

Scope of this module: decode and verify a bearer token, and turn verified claims into a `Principal`.
It does not issue tokens for production users — that belongs to an identity provider.

Blocker, stated plainly: there is no IdP wired up yet. Development tokens are self-signed with
`JWT_SECRET` via `scripts/dev_token.py`. That is acceptable for local work and unacceptable for a
deployment that holds factory data, because the same secret then authenticates everyone. Recorded
as security finding SEC-002 and tracked in docs/security-review.md.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

from core.config import get_settings
from core.errors import Unauthenticated
from core.security import Principal

REQUIRED_CLAIMS = ("sub", "org", "role", "exp")


def decode_token(token: str) -> Principal:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError as exc:
        # Reason withheld from the client: distinguishing "expired" from "bad signature" helps an
        # attacker more than it helps a legitimate caller.
        raise Unauthenticated("Invalid or expired credentials.") from exc

    missing = [claim for claim in REQUIRED_CLAIMS if claim not in claims]
    if missing:
        raise Unauthenticated("Token is missing required claims.")

    try:
        return Principal(
            user_id=UUID(str(claims["sub"])),
            organization_id=UUID(str(claims["org"])),
            role=str(claims["role"]),
        )
    except (ValueError, TypeError) as exc:
        raise Unauthenticated("Token claims are not well formed.") from exc


def issue_dev_token(user_id: UUID, organization_id: UUID, role: str, ttl_minutes: int = 60) -> str:
    """Development only. See SEC-002."""
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
