"""Shared industrial contracts.

Lives outside `apps/api` because two very different producers must agree on it exactly: the
telemetry simulator (research) and the ingestion endpoint (production). If they diverge, the
simulator stops being a valid test of the ingest path, and every synthetic-model result becomes
unverifiable.
"""
