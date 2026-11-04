# ThreadMind AI

**Autonomous Textile Factory Intelligence Platform**

ThreadMind AI is a research platform that connects fabric quality inspection, machine telemetry,
production records, and maintenance history into one industrial data layer, then reasons over that
layer with specialized ML models and a coordinated multi-agent layer.

The question it is built to answer is not only *"what defect occurred?"* but:

> What happened, where did it happen, which operational conditions were associated with it,
> what evidence supports the possible explanation, and what should the responsible engineer
> investigate next?

> **Status:** Foundation baseline v1.0. Scaffolding and requirements are in place; models and
> services are under active development. Everything in `docs/` is a specification, not a claim
> of achieved performance.

---

## What is in the box

| Component | Path | State |
|---|---|---|
| Business + software requirements | `docs/` | Baseline v1.0 |
| PostgreSQL schema | `database/schemas/001_initial.sql` | Implemented (DDL) |
| FastAPI application layer | `apps/api` | Skeleton |
| Next.js dashboard | `apps/web` | Skeleton |
| Fabric defect vision service | `ai-services/vision` | Planned |
| Predictive maintenance service | `ai-services/predictive-maintenance` | Planned |
| Root cause engine | `ai-services/root-cause` | Planned |
| Five-agent orchestration | `agents` | Contracts + graph skeleton |
| Research harness | `research/` | Planned |

## The five agents

1. **Quality Intelligence** — interprets fabric inspection output, tracks defect trends.
2. **Predictive Maintenance** — scores machine condition, ranks failure risk.
3. **Root Cause Analysis** — correlates visual defects with telemetry and maintenance events.
4. **Production Optimization** — bottlenecks, throughput, waste, OEE.
5. **Factory Intelligence Orchestrator** — decomposes a question, delegates, validates evidence.

The orchestrator validates schemas, evidence references, timestamps, model versions, and tenant
permissions. No agent may issue machine-control commands. Human approval is mandatory for
consequential recommendations.

## Design commitments

- **Numbers come from models, not prose.** An LLM never invents a sensor reading, a defect
  detection, or a failure probability. Numerical output originates from a validated model or a
  deterministic calculation.
- **Correlation is not causation.** Every investigation separates observed facts, statistical
  associations, and unverified hypotheses.
- **Tenant isolation is enforced server-side.** A client-supplied `organization_id` is never
  trusted.
- **Evidence is citable.** Each claim carries a reference to the record that supports it.

## Quick start (development)

```bash
cp .env.example .env
docker compose up --build          # postgres + redis + api + web
open http://localhost:3000         # dashboard
open http://localhost:8000/docs    # API reference
```

Apply the schema:

```bash
psql "$DATABASE_URL" -f database/schemas/001_initial.sql
```

## Requirements

Python 3.11+, Node 20+, Docker 24+.

## Documentation

- [`docs/BRD.md`](docs/BRD.md) — business requirements
- [`docs/SRS.md`](docs/SRS.md) — functional and non-functional requirements
- [`docs/architecture.md`](docs/architecture.md) — system and deployment architecture
- [`docs/database.md`](docs/database.md) — data model and engineering rules
- [`docs/API.md`](docs/API.md) — API surface
- [`docs/deployment.md`](docs/deployment.md) — cloud deployment
- [`docs/research.md`](docs/research.md) — research questions and experimental design
- [`docs/datasets.md`](docs/datasets.md) — dataset inventory and governance

## Scope boundaries

In scope: cloud factory intelligence, computer vision quality inspection, machine anomaly
detection, predictive maintenance, root cause investigation, production analytics, agent
workflows with human approval, enterprise dashboard.

Out of scope for the initial research implementation: autonomous physical machine control,
certified industrial safety control, replacement of ERP/MES, guaranteed failure prediction, and
unvalidated causal claims.

## License

MIT. Datasets retain their own licenses — see [`docs/datasets.md`](docs/datasets.md). Third-party
dataset licenses control whether a model trained on them may be used commercially.
