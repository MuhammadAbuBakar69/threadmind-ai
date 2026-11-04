"""Verification of Clerk session tokens.

Why this module exists: until now the API trusted tokens it signed itself with a shared
`JWT_SECRET` (SEC-002). That is a single secret standing between an attacker and every tenant in
the system. With Clerk, the private key never leaves Clerk, and this service holds only the public
keys, fetched from Clerk's JWKS endpoint.

Three failure modes are handled explicitly, because each has a known exploitation:

1. **Algorithm confusion.** A verifier that honours the token's `alg` header will happily accept an
   `HS256` token whose "secret" is the published RSA public key. Only `RS256` is accepted here, and
   the header's `alg` is checked before the key is even fetched.
2. **`alg: none`.** Some JWT libraries accept an unsecured token if the key is falsy. The algorithm
   allow-list rejects it before verification.
3. **Stale keys after rotation.** Clerk rotates signing keys. A `kid` that is not in the cached
   JWKS triggers exactly one refetch, so a rotation does not produce a wave of 401s, and a token
   with a forged `kid` cannot force unbounded refetches.

What this module deliberately does not do: it does not decide the caller's role. Clerk's
`org_role` is a label in Clerk's domain. The authoritative role is `organization_members.role` in
our database, resolved in `core.identity`. A token can choose which membership is in play; it can
never elevate one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.jwk import construct

from core.errors import Unauthenticated

ALLOWED_ALGORITHMS = ("RS256",)
JWKS_CACHE_TTL_SECONDS = 300.0

# kid -> (jwk dict, fetched_at). Module-level because the cache must outlive one request; a
# per-request cache would refetch the key set on every call.
_jwks_cache: dict[str, tuple[dict[str, dict[str, Any]], float]] = {}


@dataclass(frozen=True)
class ClerkIdentity:
    """A verified caller, in Clerk's vocabulary only."""

    provider_user_id: str
    provider_org_id: str | None
    session_id: str | None


def jwks_url(issuer: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


def _fetch_jwks(url: str, *, timeout: float = 5.0) -> dict[str, dict[str, Any]]:
    """Fetch a JWKS and index it by kid.

    Split out from verification so tests can substitute a local key set without network access.
    """
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    keys = {}
    for jwk in payload.get("keys", []):
        kid = jwk.get("kid")
        if kid:
            keys[kid] = jwk
    return keys


def _keys_for(url: str, *, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    now = time.monotonic()
    cached = _jwks_cache.get(url)

    if cached and not force_refresh:
        keys, fetched_at = cached
        if now - fetched_at < JWKS_CACHE_TTL_SECONDS:
            return keys

    try:
        keys = _fetch_jwks(url)
    except Exception as exc:  # network, TLS, malformed JSON
        # If Clerk is unreachable, an in-date cache is still better than rejecting every request.
        if cached:
            return cached[0]
        raise Unauthenticated("Identity provider is unreachable.") from exc

    _jwks_cache[url] = (keys, now)
    return keys


def clear_cache() -> None:
    """Test helper. Also useful when an operator needs to force a key refetch."""
    _jwks_cache.clear()


def verify_clerk_token(token: str, *, issuer: str, jwks: str | None = None,
                       authorized_parties: tuple[str, ...] = ()) -> ClerkIdentity:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise Unauthenticated("Malformed credentials.") from exc

    algorithm = header.get("alg")
    if algorithm not in ALLOWED_ALGORITHMS:
        # Checked before any key lookup: an attacker does not get to choose the algorithm.
        raise Unauthenticated("Malformed credentials.")

    kid = header.get("kid")
    if not kid:
        raise Unauthenticated("Malformed credentials.")

    url = jwks_url(issuer, jwks)
    keys = _keys_for(url)
    jwk = keys.get(kid)

    if jwk is None:
        # Exactly one refetch: key rotation is real, forced refetching is a denial-of-service lever.
        jwk = _keys_for(url, force_refresh=True).get(kid)
    if jwk is None:
        raise Unauthenticated("Malformed credentials.")

    try:
        key = construct(jwk, algorithm)
        claims = jwt.decode(
            token,
            key,
            algorithms=list(ALLOWED_ALGORITHMS),
            issuer=issuer,
            options={"require_exp": True, "require_sub": True, "verify_aud": False},
        )
    except JWTError as exc:
        raise Unauthenticated("Invalid or expired credentials.") from exc

    if authorized_parties:
        azp = claims.get("azp")
        # azp identifies the origin the token was minted for. Without this check a token minted for
        # a different property in the same Clerk application is replayable here.
        if azp is not None and azp not in authorized_parties:
            raise Unauthenticated("Invalid or expired credentials.")

    subject = claims.get("sub")
    if not subject:
        raise Unauthenticated("Token is missing required claims.")

    return ClerkIdentity(
        provider_user_id=str(subject),
        provider_org_id=claims.get("org_id") or claims.get("org"),
        session_id=claims.get("sid"),
    )
