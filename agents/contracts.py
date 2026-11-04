"""Agent communication contracts.

Every agent reads and writes these shapes. The orchestrator validates them before acting on any
output — schema, evidence references, timestamps, model version, tenant scope. A contract that
fails validation is rejected; it is never quietly coerced into something plausible.

Design rule carried by `claim_kind`: the difference between what was observed, what correlates,
and what is merely hypothesised must survive serialization. That distinction is the project's
central claim (FR-035) and it is easy to lose in free text.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AgentName(StrEnum):
    QUALITY = "quality_intelligence"
    MAINTENANCE = "predictive_maintenance"
    ROOT_CAUSE = "root_cause"
    PRODUCTION = "production_optimization"
    ORCHESTRATOR = "factory_intelligence_orchestrator"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


class ClaimKind(StrEnum):
    OBSERVED_FACT = "observed_fact"
    ASSOCIATION = "association"
    HYPOTHESIS = "hypothesis"


class AgentRequest(BaseModel):
    """Inbound work item. Tenant scope is always explicit and already authorized upstream."""

    organization_id: UUID
    factory_id: UUID | None = None
    machine_id: UUID | None = None
    batch_id: UUID | None = None
    event_type: str
    event_timestamp: datetime
    evidence_refs: list[UUID] = Field(default_factory=list)
    requested_action: str


class EvidenceRef(BaseModel):
    """A citation. `source_record_id` points at a real row; there is no free-text-only evidence."""

    evidence_type: Literal["sensor_window", "inspection", "maintenance", "batch", "document", "prediction"]
    source_record_id: UUID
    description: str = Field(max_length=1000)
    relevance_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime | None = None


class Finding(BaseModel):
    """One claim, tagged with what kind of claim it is."""

    statement: str = Field(max_length=2000)
    claim_kind: ClaimKind
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def non_hypothesis_needs_evidence(self) -> Finding:
        """Facts and associations are citations. A hypothesis may stand alone, clearly labelled."""
        if self.claim_kind in (ClaimKind.OBSERVED_FACT, ClaimKind.ASSOCIATION) and not self.evidence:
            raise ValueError(
                "observed facts and associations require at least one evidence reference (FR-034)"
            )
        return self


class AgentOutput(BaseModel):
    agent: AgentName
    status: RunStatus
    model_version_id: UUID | None = None
    model_name: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    recommended_next_step: str | None = None
    requires_human_approval: bool = False
    token_usage: int | None = None
    error: str | None = None

    @model_validator(mode="after")
    def failed_runs_claim_nothing(self) -> AgentOutput:
        """A run that did not succeed has nothing to report. Silence is the honest output."""
        if self.status is RunStatus.FAILED and self.findings:
            raise ValueError("a failed run must not report findings")
        return self

    def validate_against(self, request: AgentRequest) -> None:
        """Reject outputs that cite evidence from another tenant or an unrelated event.

        Full referential validation happens against the database; this is the cheap structural
        gate the orchestrator applies before it trusts anything (FR-042, FR-048).
        """
        if self.status is RunStatus.FAILED:
            return
        for finding in self.findings:
            for ev in finding.evidence:
                if ev.relevance_score <= 0:
                    raise ValueError(f"evidence {ev.source_record_id} has no relevance")


AGENT_PERMITTED_TOOLS: dict[AgentName, tuple[str, ...]] = {
    AgentName.QUALITY: ("vision.inspect", "quality.read_history", "quality.write_result"),
    AgentName.MAINTENANCE: ("sensors.read_window", "model.anomaly", "model.failure_risk", "maintenance.read"),
    AgentName.ROOT_CAUSE: ("quality.read", "sensors.read_window", "maintenance.read", "docs.retrieve", "stats.correlate"),
    AgentName.PRODUCTION: ("production.read", "analytics.oee", "forecast.run"),
    AgentName.ORCHESTRATOR: ("agents.delegate", "evidence.validate"),
}

# FR-048: no agent, at any point, holds a tool that can command machinery.
FORBIDDEN_TOOL_PREFIXES = ("machine.control", "plc.write", "scada.", "actuator.")


def assert_tool_allowed(agent: AgentName, tool: str) -> None:
    if tool.startswith(FORBIDDEN_TOOL_PREFIXES):
        raise PermissionError(f"{agent} may never call {tool}: decision support only (FR-048)")
    if tool not in AGENT_PERMITTED_TOOLS[agent]:
        raise PermissionError(f"{agent} is not permitted to call {tool}")
