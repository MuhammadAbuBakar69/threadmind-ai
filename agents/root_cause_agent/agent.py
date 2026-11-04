"""Agent 3 — Root Cause Analysis.

The research centre of the project. This agent assembles the evidence window around an event,
compares it with historical normal operation, retrieves technical documentation, and ranks
candidate explanations using an explicit scoring method.

Two hard constraints, both enforced in code rather than in prompt wording:

* Confidence is computed by the ranking function, never narrated by the LLM (FR-034).
* Every explanation is tagged `observed_fact`, `association` or `hypothesis` (FR-035), because the
  failure mode of LLM-written analysis is stating correlation as causation.
"""

from __future__ import annotations

from agents.contracts import AgentName, AgentOutput, AgentRequest

NAME = AgentName.ROOT_CAUSE


async def run(request: AgentRequest) -> AgentOutput:
    """Workflow (FR-030 → FR-036).

    1. Resolve the machines and batches implicated by the event.
    2. Retrieve the operational time window around the event timestamp.
    3. Identify abnormal patterns and change points.
    4. Compare against historical normal periods for the same machine and fabric type.
    5. Correlate defect frequency with maintenance events.
    6. Generate candidate explanations; score them with the evidence-ranking function.
    7. Retrieve relevant technical documentation for the top candidates.
    8. Emit the report with supporting *and* contradictory evidence, then request engineer review.
    """
    raise NotImplementedError(
        "Phase 5 (weeks 15-18): implement the correlation and ranking core first"
    )
