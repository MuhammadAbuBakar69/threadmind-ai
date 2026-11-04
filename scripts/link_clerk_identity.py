"""Link a Clerk account to a local organization and role.

Why this exists: Clerk answers "who is this", not "which tenant, with which role". That second
question is answered by our own tables, and this script is how those rows are created until the
Clerk membership webhook does it automatically (issue #20).

Usage
-----
    python scripts/link_clerk_identity.py \\
        --email owner@factory.example \\
        --clerk-user-id user_2abcDEF123 \\
        --clerk-org-id org_2xyzORG456 \\
        --org-name "Karachi Weaving Mills" \\
        --role factory_admin

Idempotent: re-running with the same arguments updates the link instead of creating a duplicate,
which matters because operator scripts get run twice after a failed deploy.

Deliberately not automatic. A script that creates tenants on first signup means an unauthenticated
stranger can create an organization by signing up, and every such row is a support ticket later.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from core.security import ROLE_RANK  # noqa: E402
from db import get_sessionmaker  # noqa: E402
from sqlalchemy import text  # noqa: E402


def link(*, email: str, clerk_user_id: str, clerk_org_id: str, org_name: str, role: str) -> str:
    session = get_sessionmaker()()
    try:
        org_id = session.execute(
            text(
                """
                INSERT INTO organizations (name, clerk_org_id)
                VALUES (:name, :clerk_org_id)
                ON CONFLICT (clerk_org_id) DO UPDATE SET name = organizations.name
                RETURNING id
                """
            ),
            {"name": org_name, "clerk_org_id": clerk_org_id},
        ).scalar_one()

        user_id = session.execute(
            text(
                """
                INSERT INTO users (email, authentication_provider_id)
                VALUES (:email, :provider_id)
                ON CONFLICT (authentication_provider_id) DO UPDATE
                    SET email = EXCLUDED.email
                RETURNING id
                """
            ),
            {"email": email, "provider_id": clerk_user_id},
        ).scalar_one()

        session.execute(
            text(
                """
                INSERT INTO organization_members (organization_id, user_id, role)
                VALUES (:org_id, :user_id, :role)
                ON CONFLICT (organization_id, user_id) DO UPDATE SET role = EXCLUDED.role
                """
            ),
            {"org_id": org_id, "user_id": user_id, "role": role},
        )

        session.commit()
        return f"linked {email} ({clerk_user_id}) to {org_name} ({org_id}) as {role}"
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--clerk-user-id", required=True)
    parser.add_argument("--clerk-org-id", required=True)
    parser.add_argument("--org-name", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ROLE_RANK))
    args = parser.parse_args()

    print(
        link(
            email=args.email,
            clerk_user_id=args.clerk_user_id,
            clerk_org_id=args.clerk_org_id,
            org_name=args.org_name,
            role=args.role,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
