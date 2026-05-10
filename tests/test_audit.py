"""Smoke test for the AuditResult aggregation and scoring."""

from __future__ import annotations

from datetime import UTC, datetime

from ncc.audit import AuditResult
from ncc.checks import Finding, Severity


def _finding(severity: Severity, check_id: str = "x") -> Finding:
    return Finding(
        check_id=check_id,
        severity=severity,
        title="t",
        detail="d",
    )


def test_clean_audit_scores_100() -> None:
    now = datetime.now(UTC)
    audit = AuditResult(started_at=now, finished_at=now)
    assert audit.score == 100


def test_one_critical_drops_score_significantly() -> None:
    now = datetime.now(UTC)
    audit = AuditResult(started_at=now, finished_at=now, findings=[_finding(Severity.CRITICAL)])
    assert audit.score == 75


def test_score_floors_at_zero() -> None:
    now = datetime.now(UTC)
    audit = AuditResult(
        started_at=now,
        finished_at=now,
        findings=[_finding(Severity.CRITICAL) for _ in range(20)],
    )
    assert audit.score == 0


def test_score_is_none_when_any_check_errored() -> None:
    """Regression: a Notion 401 used to produce score=100 because errors
    were not subtracted. Now an incomplete audit returns None."""
    now = datetime.now(UTC)
    audit = AuditResult(
        started_at=now,
        finished_at=now,
        findings=[],
        errors={"public_access": "401 unauthorized"},
    )
    assert audit.score is None
    assert audit.is_complete is False
    assert "N/A" in audit.summary_line()


def test_grouping_by_severity() -> None:
    now = datetime.now(UTC)
    findings = [
        _finding(Severity.CRITICAL),
        _finding(Severity.HIGH),
        _finding(Severity.HIGH),
        _finding(Severity.LOW),
    ]
    audit = AuditResult(started_at=now, finished_at=now, findings=findings)
    assert len(audit.by_severity[Severity.CRITICAL]) == 1
    assert len(audit.by_severity[Severity.HIGH]) == 2
    assert len(audit.by_severity[Severity.LOW]) == 1
    assert len(audit.by_severity[Severity.MEDIUM]) == 0


def test_finding_serializes_to_dict() -> None:
    f = _finding(Severity.HIGH, check_id="public_access")
    d = f.to_dict()
    assert d["check_id"] == "public_access"
    assert d["severity"] == "high"
