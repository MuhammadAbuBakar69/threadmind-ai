# agents/ — Multi-agent intelligence layer

LangGraph orchestration over five cooperating agents. The framework matters less than the
constraints, so the constraints are in code:

| Constraint | Where | Requirement |
|---|---|---|
| Agent I/O is typed and validated | `contracts.py` | FR-044 |
| Observed / association / hypothesis never blur | `contracts.py::ClaimKind` | FR-035 |
| Facts and associations must cite evidence | `contracts.py::Finding` | FR-034 |
| No agent can command machinery | `contracts.py::assert_tool_allowed` | FR-048 |
| Consequential output stops for a human | `AgentOutput.requires_human_approval` | FR-047 |
| Orchestrator validates, never trusts | `orchestrator/graph.py::validate_output` | FR-042 |

## Agents

| Agent | Module | Reads | Produces |
|---|---|---|---|
| Quality Intelligence | `quality_agent/agent.py` | image, batch, machine, quality history | classifications, localization, quality report |
| Predictive Maintenance | `maintenance_agent/agent.py` | sensors, machine profile, maintenance | anomaly score, risk category, recommendation |
| Root Cause Analysis | `root_cause_agent/agent.py` | quality + telemetry + production + maintenance + docs | ranked hypotheses with evidence |
| Production Optimization | `production_agent/agent.py` | production metrics, downtime, utilization | bottlenecks, forecasts, OEE |
| Factory Orchestrator | `orchestrator/graph.py` | user question or factory event | validated consolidated answer |

## Why not one big agent

A single general-purpose LLM asked to diagnose a fabric defect will produce fluent text with no
provenance. Splitting into specialists with typed contracts makes each claim falsifiable: you can
point at the sensor row, the image record, and the model version behind it. Experiment E3 is
designed to test whether that actually helps, rather than asserting it does (RQ4).
