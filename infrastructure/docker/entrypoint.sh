#!/bin/sh
# Container entrypoint.
#
# Migrating on start is convenient and slightly risky: a bad migration takes the service down at the
# same moment it deploys. That trade is right for this project (single documented migration path,
# advisory-locked, idempotent) and wrong for a system with zero-downtime requirements. Set
# RUN_MIGRATIONS=0 and run `python migrate.py` from a release job if that ever changes.
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "applying migrations"
  python /app/migrate.py
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
