"""Agent 5 — Factory Intelligence Orchestrator.

The only entry point for multi-agent work. It decomposes a question or factory event, delegates to
the specialized agents, then *validates* what comes back. The orchestrator does not trust an agent
because it returned successfully: it checks the contract, the model version, the evidence
references, the timestamps, and the tenant scope.

LangGraph state machine, deliberately explicit rather than a free agent loop: an unconstrained
loop over industrial data can produce a confident answer with no traceable evidence, which is the
exact failure mode this project exists to avoid (RQ4, H4).
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from agents.contracts import AgentName, AgentOutput, AgentRequest


class OrchestratorState(TypedDict, total=False):
    request: AgentRequest
    intent: str
    plan: list[AgentName]
    outputs: Annotated[list[AgentOutput], "agent outputs, validated on arrival"]
    validation_errors: list[str]
    requires_human_approval: bool
    final_summary: str
    retries: int


VALIDATION_STEPS = (
    "schema",  # contract shape
    "tenant_scope",  # every evidence ref resolves inside the org
    "model_version",  # numeric claims trace to a recorded artifact
    "timestamps",  # evidence precedes or brackets the event
    "claim_kinds",  # no association dressed as fact
)


def classify_intent(request: AgentRequest) -> str:
    raise NotImplementedError("Phase 5: intent classifier over the SRS event vocabulary")


def build_plan(intent: str) -> list[AgentName]:
    raise NotImplementedError("Phase 5: map intent to the minimum sufficient agent set")


def validate_output(output: AgentOutput, request: AgentRequest) -> list[str]:
    """Return validation errors. An empty list means the output may be consolidated."""
    errors: list[str] = []
    try:
        output.validate_against(request)
    except ValueError as exc:
        errors.append(str(exc))
    if output.status.value == "succeeded" and request.requested_action and not output.findings:
        errors.append(f"{output.agent} succeeded without findings")
    return errors


def route(state: OrchestratorState) -> Literal["delegate", "consolidate", "human_review", "fail"]:
    if state.get("validation_errors"):
        return "fail" if state.get("retries", 0) >= 2 else "delegate"
    if state.get("requires_human_approval"):
        return "human_review"
    return "consolidate"
