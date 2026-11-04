"""Verification tests for Clerk session tokens.

These run without network access and without Clerk: a local RSA key pair stands in for Clerk's
signing key. The point is to pin the behaviours that have known exploits behind them (algorithm
confusion, unsecured tokens, key-rotation storms) rather than to test the JWT library.

A token that verifies is not enough here. Each rejection test asserts *why* it was rejected by
checking the fetch behaviour too, so a verifier that rejected everything for the wrong reason would
still fail.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from core import clerk
from core.clerk import verify_clerk_token
from core.errors import Forbidden, Unauthenticated
from core.identity import resolve_principal
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

ISSUER = "https://threadmind-test.clerk.accounts.dev"
KID = "test-key-1"


def _b64u(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def rsa_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    public_der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": KID,
        "use": "sig",
        "alg": "RS256",
        "n": _b64u(numbers.n),
        "e": _b64u(numbers.e),
    }
    return {
        "private_pem": private_pem,
        "public_pem": public_pem,
        "public_der": public_der,
        "jwk": jwk,
    }


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_keys):
    """Serve a local key set and count fetches, so caching and rotation are observable."""
    calls: list[bool] = []

    def fake_fetch(url, *, timeout=5.0):
        calls.append(True)
        return {KID: rsa_keys["jwk"]}

    monkeypatch.setattr(clerk, "_fetch_jwks", fake_fetch)
    clerk.clear_cache()
    yield calls
    clerk.clear_cache()


def _claims(**overrides):
    now = datetime.now(UTC)
    claims = {
        "sub": "user_2abcDEF123",
        "org_id": "org_2xyzORG456",
        "sid": "sess_abc",
        "iss": ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    claims.update(overrides)
    return claims


def _sign(claims, private_pem, *, kid=KID, algorithm="RS256"):
    return jwt.encode(claims, private_pem, algorithm=algorithm, headers={"kid": kid})


def test_a_valid_token_yields_the_provider_identity(rsa_keys):
    token = _sign(_claims(), rsa_keys["private_pem"])
    identity = verify_clerk_token(token, issuer=ISSUER)

    assert identity.provider_user_id == "user_2abcDEF123"
    assert identity.provider_org_id == "org_2xyzORG456"
    assert identity.session_id == "sess_abc"


def test_the_legacy_org_claim_is_accepted(rsa_keys):
    """Clerk has shipped both `org_id` and `org`; a token from either must not be rejected."""
    claims = _claims()
    claims.pop("org_id")
    claims["org"] = "org_2xyzORG456"

    identity = verify_clerk_token(_sign(claims, rsa_keys["private_pem"]), issuer=ISSUER)
    assert identity.provider_org_id == "org_2xyzORG456"


def test_a_token_without_an_organization_is_still_a_valid_identity(rsa_keys):
    claims = _claims()
    claims.pop("org_id")

    identity = verify_clerk_token(_sign(claims, rsa_keys["private_pem"]), issuer=ISSUER)
    assert identity.provider_org_id is None


def test_an_unsecured_token_is_rejected(rsa_keys):
    """`alg: none` must never reach verification, whatever the key material."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "kid": KID}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps(_claims()).encode()).rstrip(b"=")
    token = f"{header.decode()}.{payload.decode()}."

    with pytest.raises(Unauthenticated):
        verify_clerk_token(token, issuer=ISSUER)


def test_algorithm_confusion_is_rejected_before_any_key_lookup(rsa_keys, patch_jwks):
    """An HS256 token whose secret is the published RSA public key is the classic break.

    The verifier must reject on the `alg` header alone, so no key is ever fetched.
    """
    # Signed with the raw public-key bytes as the HMAC secret. python-jose refuses to do this with a
    # PEM string ("should not be used for HMAC") but accepts DER, and an attacker is not obliged to
    # use python-jose at all - they would HMAC with whatever bytes the JWKS publishes.
    token = _sign(_claims(), rsa_keys["public_der"], algorithm="HS256")

    with pytest.raises(Unauthenticated):
        verify_clerk_token(token, issuer=ISSUER)
    assert patch_jwks == []


def test_an_expired_token_is_rejected(rsa_keys):
    claims = _claims()
    claims["exp"] = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
    claims["iat"] = int((datetime.now(UTC) - timedelta(minutes=30)).timestamp())

    with pytest.raises(Unauthenticated):
        verify_clerk_token(_sign(claims, rsa_keys["private_pem"]), issuer=ISSUER)


def test_a_token_from_another_issuer_is_rejected(rsa_keys):
    token = _sign(_claims(iss="https://somewhere-else.example"), rsa_keys["private_pem"])

    with pytest.raises(Unauthenticated):
        verify_clerk_token(token, issuer=ISSUER)


def test_an_unknown_kid_triggers_exactly_one_refetch(rsa_keys, patch_jwks):
    """Key rotation must be survivable; a forged kid must not become a fetch amplifier."""
    token = _sign(_claims(), rsa_keys["private_pem"], kid="rotated-key-not-in-cache")

    with pytest.raises(Unauthenticated):
        verify_clerk_token(token, issuer=ISSUER)

    assert len(patch_jwks) == 2, "expected the initial fetch plus one refetch"


def test_a_warm_cache_does_not_refetch(rsa_keys, patch_jwks):
    token = _sign(_claims(), rsa_keys["private_pem"])

    verify_clerk_token(token, issuer=ISSUER)
    verify_clerk_token(token, issuer=ISSUER)
    verify_clerk_token(token, issuer=ISSUER)

    assert len(patch_jwks) == 1


def test_azp_must_match_an_authorized_party_when_configured(rsa_keys):
    token = _sign(_claims(azp="https://evil.example"), rsa_keys["private_pem"])

    with pytest.raises(Unauthenticated):
        verify_clerk_token(
            token, issuer=ISSUER, authorized_parties=("https://app.threadmind.example",)
        )


def test_a_matching_azp_is_accepted(rsa_keys):
    token = _sign(_claims(azp="https://app.threadmind.example"), rsa_keys["private_pem"])

    identity = verify_clerk_token(
        token, issuer=ISSUER, authorized_parties=("https://app.threadmind.example",)
    )
    assert identity.provider_user_id == "user_2abcDEF123"


def test_a_garbage_token_is_rejected(rsa_keys):
    for token in ("not-a-token", "a.b.c", "....", ""):
        with pytest.raises(Unauthenticated):
            verify_clerk_token(token, issuer=ISSUER)


def test_jwks_url_is_derived_from_the_issuer():
    assert clerk.jwks_url(ISSUER) == f"{ISSUER}/.well-known/jwks.json"
    assert clerk.jwks_url(ISSUER + "/") == f"{ISSUER}/.well-known/jwks.json"
    assert clerk.jwks_url(ISSUER, "https://keys.example/jwks.json") == "https://keys.example/jwks.json"


# ---------------------------------------------------------------------------
# Identity resolution: the provider says who you are, the database says what you may touch.
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    def __init__(self, row):
        self._row = row
        self.statements = []

    def execute(self, statement, params):
        self.statements.append((str(statement), params))
        return _FakeResult(self._row)


def test_no_organization_selected_is_forbidden_not_unauthenticated():
    """403, because the credentials are valid: the account simply has no organization in play."""
    with pytest.raises(Forbidden):
        resolve_principal(_FakeSession(None), provider_user_id="user_1", provider_org_id=None)


def test_an_unknown_membership_is_forbidden():
    with pytest.raises(Forbidden):
        resolve_principal(_FakeSession(None), provider_user_id="user_1", provider_org_id="org_1")


def test_a_membership_resolves_to_a_local_principal():
    user_id, org_id = uuid4(), uuid4()
    session = _FakeSession((user_id, org_id, "factory_manager"))

    principal = resolve_principal(
        session, provider_user_id="user_2abcDEF123", provider_org_id="org_2xyzORG456"
    )

    assert principal.user_id == user_id
    assert principal.organization_id == org_id
    assert principal.role == "factory_manager"
    assert principal.at_least("quality_inspector")
    assert not principal.at_least("factory_admin")


def test_the_authoritative_role_comes_from_the_database_not_the_token():
    """The resolver never reads a role from claims; it selects one from organization_members.

    This test guards the design decision: if someone later "optimises" the resolver by trusting a
    role claim, this fails.
    """
    row = (uuid4(), uuid4(), "quality_inspector")
    principal = resolve_principal(
        _FakeSession(row), provider_user_id="user_1", provider_org_id="org_1"
    )
    assert principal.role == "quality_inspector"
    assert not principal.at_least("factory_manager")
