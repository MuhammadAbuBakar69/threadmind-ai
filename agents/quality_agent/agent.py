"""Agent 1 — Quality Intelligence.

Owns the interpretation of fabric inspection output. It calls the vision service (a model), reads
historical quality context, and returns a structured quality report. It does not decide defect
classes itself: the class and confidence come from the recorded model version.
"""

from __future__ import annotations

from agents.contracts import AgentName, AgentOutput, AgentRequest

NAME = AgentName.QUALITY


async def run(request: AgentRequest) -> AgentOutput:
    """Workflow (FR-013 → FR-021).

    1. Validate the image reference and production identifiers.
    2. Call the fabric vision model via `vision.inspect`.
    3. Persist predictions with the model version.
    4. Compare against historical defect trends for the machine and line.
    5. Produce the structured report; flag uncertain classifications for inspector review.
    """
    raise NotImplementedError(
        "Phase 3 (weeks 7-10): implement once the vision service exposes /inspect"
    )
