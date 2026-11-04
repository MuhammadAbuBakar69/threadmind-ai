"""Agent 4 — Production Optimization.

Owns bottlenecks, throughput, waste, and OEE. OEE is computed, not estimated: availability,
performance and quality each use an explicit, testable definition so two people reading the same
dashboard get the same number.
"""

from __future__ import annotations

from agents.contracts import AgentName, AgentOutput, AgentRequest

NAME = AgentName.PRODUCTION


async def run(request: AgentRequest) -> AgentOutput:
    """Workflow (FR-037 → FR-041).

    1. Retrieve production records for the requested window.
    2. Compute OEE components from explicit definitions.
    3. Identify bottlenecks by comparing line and machine performance.
    4. Forecast production trends.
    5. Generate improvement scenarios with expected impact where it is genuinely calculable.
    """
    raise NotImplementedError("Phase 5: implement after the analytics engine exists")
