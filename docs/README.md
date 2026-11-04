# Documentation

| Document | Purpose |
|---|---|
| [`BRD.md`](BRD.md) | Business problem, stakeholders, success criteria, business model |
| [`SRS.md`](SRS.md) | FR-001 → FR-058 with non-functional requirements and acceptance criteria |
| [`architecture.md`](architecture.md) | Layers, event boundary, deployment, agent topology |
| [`database.md`](database.md) | Data model, engineering rules, tenant isolation |
| [`API.md`](API.md) | Endpoint surface mapped to requirements |
| [`deployment.md`](deployment.md) | Local stack, cloud topology, operations |
| [`research.md`](research.md) | Research questions, hypotheses, experiments, threats to validity |
| [`datasets.md`](datasets.md) | Dataset inventory, governance, licensing |
| [`repository-audit.md`](repository-audit.md) | Audit: what is verified, what is not, findings, remediation |
| [`architecture-review.md`](architecture-review.md) | Architecture verdict, invariants, rejected alternatives |
| [`security-review.md`](security-review.md) | Threat model, SEC findings with status, controls |
| [`production-readiness.md`](production-readiness.md) | Honest readiness checklist and deception checklist |
| [`implementation-roadmap.md`](implementation-roadmap.md) | Phased plan with executable exit conditions |
| [`issue-traceability.md`](issue-traceability.md) | Every issue mapped to what actually exists |
| [`testing-strategy.md`](testing-strategy.md) | Claims → tests, what runs where, stated gaps |
| [`research-reproducibility.md`](research-reproducibility.md) | Seeds, manifests, splits, metric definitions |
| [`operations-runbook.md`](operations-runbook.md) | Deploy, backup/restore, incidents, local stack |

Start with the audit. It is the only document here that was written by checking the code instead of
describing it.

Requirement IDs are the audit spine. An issue, pull request, or test that does not name the ID it
satisfies is harder to review and easier to quietly drop.
