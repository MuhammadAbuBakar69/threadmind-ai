"""Contract tests.

These protect the properties that make ThreadMind's output auditable rather than merely readable.
If one of these fails, the platform is producing text it cannot defend.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agents.contracts import (
    AgentName,
    AgentOutput,
    AgentRequest,
    ClaimKind,
    EvidenceRef,
    Finding,
    RunStatus,
    assert_tool_allowed,
)


def evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_type="sensor_window",
        source_record_id=uuid4(),
        description="vibration exceeded the 30-day baseline between 09:12 and 09:40",
        relevance_score=0.81,
        timestamp=datetime(2026, 11, 4, 9, 12, tzinfo=UTC),
    )


def test_observed_fact_requires_evidence():
    with pytest.raises(ValidationError):
        Finding(statement="vibration was elevated", claim_kind=ClaimKind.OBSERVED_FACT)


def test_association_requires_evidence():
    with pytest.raises(ValidationError):
        Finding(statement="defects rose with vibration", claim_kind=ClaimKind.ASSOCIATION)


def test_hypothesis_may_stand_alone_but_is_labelled():
    finding = Finding(
        statement="possible bearing wear",
        claim_kind=ClaimKind.HYPOTHESIS,
        confidence=0.4,
    )
    assert finding.claim_kind is ClaimKind.HYPOTHESIS
    assert finding.evidence == []


def test_failed_run_cannot_report_findings():
    with pytest.raises(ValidationError):
        AgentOutput(
            agent=AgentName.ROOT_CAUSE,
            status=RunStatus.FAILED,
            findings=[
                Finding(
                    statement="defect rate doubled",
                    claim_kind=ClaimKind.OBSERVED_FACT,
                    evidence=[evidence()],
                )
            ],
        )


def test_evidence_relevance_is_bounded():
    with pytest.raises(ValidationError):
        EvidenceRef(
            evidence_type="inspection",
            source_record_id=uuid4(),
            description="cited",
            relevance_score=1.5,
        )


def test_forbidden_machine_control_tools_are_rejected_for_every_agent():
    for agent in AgentName:
        with pytest.raises(PermissionError):
            assert_tool_allowed(agent, "machine.control.set_speed")


def test_agent_cannot_use_another_agents_tool():
    with pytest.raises(PermissionError):
        assert_tool_allowed(AgentName.QUALITY, "model.failure_risk")


def test_declared_tools_are_permitted():
    assert_tool_allowed(AgentName.ROOT_CAUSE, "docs.retrieve")
    assert_tool_allowed(AgentName.PRODUCTION, "analytics.oee")


def test_validate_against_rejects_zero_relevance_evidence():
    out = AgentOutput(
        agent=AgentName.QUALITY,
        status=RunStatus.SUCCEEDED,
        findings=[
            Finding(
                statement="two holes detected",
                claim_kind=ClaimKind.OBSERVED_FACT,
                evidence=[
                    EvidenceRef(
                        evidence_type="inspection",
                        source_record_id=uuid4(),
                        description="unrelated",
                        relevance_score=0.0,
                    )
                ],
            )
        ],
    )
    request = AgentRequest(
        organization_id=uuid4(),
        event_type="quality_anomaly",
        event_timestamp=datetime(2026, 11, 4, 9, 30, tzinfo=UTC),
        requested_action="investigate_root_cause",
    )
    with pytest.raises(ValueError):
        out.validate_against(request)
