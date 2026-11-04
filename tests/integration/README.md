# Integration tests

| File | Scope | Requirements |
|---|---|---|
| `test_tenant_isolation.py` | RLS coverage, cross-tenant read/write denial, child-table inheritance, natural-key idempotency | FR-004, FR-022, FR-023 |

```bash
DATABASE_URL_TEST=postgresql+psycopg://threadmind:threadmind@localhost:5432/threadmind_test pytest tests/integration
```

These tests apply the real migrations and then connect as a **non-superuser** role, because a
superuser bypasses row-level security regardless of `FORCE`. Without that detail the suite would
pass while the deployed system leaked every tenant.

CI runs this against a PostgreSQL service container. Local runs skip cleanly when
`DATABASE_URL_TEST` is unset rather than failing confusingly.
