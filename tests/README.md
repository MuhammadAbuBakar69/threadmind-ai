# Tests

```bash
pip install -r apps/api/requirements.txt
pip install pydantic
pytest
```

| Directory | Scope | Runs today |
|---|---|---|
| `unit/` | Contracts, validation, access control, OEE math | Yes |
| `integration/` | Service-to-service flows | Phase 7 |
| `security/` | Tenant isolation, upload validation, agent scope | Phase 7 |
| `performance/` | Latency and throughput benchmarks | Phase 7 |
