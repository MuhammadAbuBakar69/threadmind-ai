"""Migration ordering tests.

The expensive failure this prevents: 900_rollback_002.sql being applied as if it were a forward
migration, which silently undid the RLS hardening on 2026-11-04. Globbing is the bug, so the glob is
what gets tested.
"""

from __future__ import annotations

from pathlib import Path

from migrate import database_dir, migration_files, schema_files


def test_rollbacks_are_never_applied_automatically(tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "002_rls_hardening.sql").write_text("-- forward")
    (migrations / "003_clerk_identity.sql").write_text("-- forward")
    (migrations / "900_rollback_002.sql").write_text("-- rollback")
    (migrations / "900_rollback_003.sql").write_text("-- rollback")
    (migrations / "README.md").write_text("notes")

    names = [p.name for p in migration_files(tmp_path)]
    assert names == ["002_rls_hardening.sql", "003_clerk_identity.sql"]


def test_migrations_are_applied_in_numeric_order(tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for name in ["010_ten.sql", "002_two.sql", "001_one.sql"]:
        (migrations / name).write_text("-- x")
    assert [p.name for p in migration_files(tmp_path)] == [
        "001_one.sql",
        "002_two.sql",
        "010_ten.sql",
    ]


def test_the_repository_has_ordered_forward_migrations_and_schema():
    directory = database_dir()
    assert schema_files(directory), "base schema missing"
    names = [p.name for p in migration_files(directory)]
    assert names, "no forward migrations found"
    assert names == sorted(names)
    assert not any("rollback" in n for n in names)


def test_rollback_wrappers_are_stripped():
    from migrate import _strip_transaction_wrappers

    # splitlines() drops the trailing newline, so the comparison is against the joined body.
    assert _strip_transaction_wrappers("BEGIN;\nSELECT 1;\nCOMMIT;\n") == "SELECT 1;"
