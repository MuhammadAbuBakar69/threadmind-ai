"""Agent 2 — Predictive Maintenance.

Owns machine condition interpretation. Sensor readings and risk scores originate from validated
models; this agent's judgement covers threshold comparison, prioritisation, and the recommendation
wording — not the numbers themselves.
"""

from __future__ import annotations

from agents.contracts import AgentName, AgentOutput, AgentRequest

NAME = AgentName.MAINTENANCE


async def run(request: AgentRequest) -> AgentOutput:
    """Workflow (FR-022 → FR-029).

    1. Validate incoming sensor measurements against expected ranges and quality flags.
    2. Pull the machine's historical operating profile.
    3. Score anomaly and failure risk with recorded model versions.
    4. Compare against configured thresholds; produce risk category.
    5. Draft a maintenance recommendation routed through human approval (FR-047).
    """
    raise NotImplementedError("Phase 4 (weeks 11-14): implement once anomaly models are trained")
