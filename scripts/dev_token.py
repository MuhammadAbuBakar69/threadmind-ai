#!/usr/bin/env python3
"""Mint a development bearer token.

Development only (SEC-002). There is no identity provider wired up yet, so this signs a token with
JWT_SECRET. Any deployment holding real factory data must replace this with a real IdP before it
accepts traffic — one shared secret authenticating every user is not authentication.

Usage:
    python scripts/dev_token.py --role factory_admin
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from core.auth import issue_dev_token  # noqa: E402
from core.security import ROLE_RANK  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Issue a development JWT.")
    parser.add_argument("--role", choices=sorted(ROLE_RANK), default="factory_admin")
    parser.add_argument("--user", default=str(uuid.uuid4()))
    parser.add_argument("--org", default=str(uuid.uuid4()))
    parser.add_argument("--ttl", type=int, default=60, help="minutes")
    args = parser.parse_args()

    token = issue_dev_token(
        user_id=uuid.UUID(args.user),
        organization_id=uuid.UUID(args.org),
        role=args.role,
        ttl_minutes=args.ttl,
    )
    print(f"user   : {args.user}")
    print(f"org    : {args.org}")
    print(f"role   : {args.role}")
    print(f"token  : {token}")
