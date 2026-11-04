# Migrations

One file per change, `NNN_short_description.sql`, applied in order and never edited after merge.

Destructive changes use a two-step deploy: add the new shape, backfill, verify, then remove the old
one in a later release. A migration that both drops and adds in one step cannot be rolled back
safely while the previous application version is still serving traffic.
