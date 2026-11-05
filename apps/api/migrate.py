"""Apply the schema and forward migrations at container start.

Why in the image rather than in a deploy pipeline: every host has a different way of running a
pre-deploy step (Render has preDeployCommand, Fly has release_command, Railway has none), and none of
them guarantee a psql client is installed. Running it here means the same code path runs on a laptop
and in production.

Two properties this must have, because a half-applied migration at 3am is worse than a slow start:

* **Idempotent.** Re-running applies nothing twice: the base schema uses IF NOT EXISTS, and each
  forward migration records itself in `schema_migrations`.
* **Single writer.** Two replicas starting together would otherwise race. A PostgreSQL advisory lock
  makes the second one wait, then find the work already done.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

LOCK_KEY = 8_814_221  # arbitrary constant; only this process must agree with itself


def database_dir() -> Path:
    override = os.getenv("DATABASE_DIR")
    if override:
        return Path(override)
    in_image = Path("/app/database")
    if in_image.is_dir():
        return in_image
    return Path(__file__).resolve().parents[2] / "database"


def schema_files(directory: Path) -> list[Path]:
    return sorted((directory / "schemas").glob("*.sql"))


def migration_files(directory: Path) -> list[Path]:
    """Forward migrations only.

    Rollbacks are named 9NN_rollback_*.sql and must never be applied automatically. Globbing [0-9]*
    here is the exact mistake that silently undid the RLS migration once already, on 2026-11-04.
    """
    return sorted(p for p in (directory / "migrations").glob("0*.sql") if p.is_file())


def _strip_transaction_wrappers(sql: str) -> str:
    """Migrations may carry their own BEGIN/COMMIT; the caller already owns the transaction."""
    lines = [ln for ln in sql.splitlines() if ln.strip().upper() not in {"BEGIN;", "COMMIT;"}]
    return "\n".join(lines)


def apply(engine, directory: Path) -> list[str]:
    applied: list[str] = []
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "  filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
        )
        for path in schema_files(directory):
            conn.exec_driver_sql(path.read_text())
            applied.append(path.name)

        done = {
            row[0] for row in conn.execute(text("SELECT filename FROM schema_migrations")).all()
        }
        for path in migration_files(directory):
            if path.name in done:
                continue
            conn.exec_driver_sql(_strip_transaction_wrappers(path.read_text()))
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"), {"f": path.name}
            )
            applied.append(path.name)
    return applied


def main() -> int:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    directory = database_dir()
    engine = create_engine(url, future=True)
    try:
        applied = apply(engine, directory)
    finally:
        engine.dispose()
    print("applied:", ", ".join(applied) if applied else "nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
