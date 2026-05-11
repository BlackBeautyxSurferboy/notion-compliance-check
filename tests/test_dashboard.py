"""Tests for the dashboard module — schema + status mapping + row construction."""

from __future__ import annotations

from datetime import UTC, datetime

from ncc.audit import AuditResult
from ncc.checks import Finding, Severity
from ncc.dashboard import _history_db_properties, _status_for


class TestHistoryDBSchema:
    def test_has_score_column(self) -> None:
        props = _history_db_properties()
        assert "Score" in props
        assert "number" in props["Score"]

    def test_has_severity_count_columns(self) -> None:
        props = _history_db_properties()
        for name in ("Critical", "High", "Medium", "Low"):
            assert name in props, f"missing severity column: {name}"

    def test_status_has_five_options(self) -> None:
        props = _history_db_properties()
        options = props["Status"]["select"]["options"]
        names = {o["name"] for o in options}
        assert names == {"Clean", "Warning", "Risk", "Critical", "Incomplete"}


class TestStatusForScore:
    def test_none_score_is_incomplete(self) -> None:
        assert _status_for(None) == "Incomplete"

    def test_high_score_is_clean(self) -> None:
        assert _status_for(95) == "Clean"
        assert _status_for(90) == "Clean"

    def test_mid_score_is_warning(self) -> None:
        assert _status_for(75) == "Warning"

    def test_low_score_is_risk(self) -> None:
        assert _status_for(50) == "Risk"

    def test_very_low_score_is_critical(self) -> None:
        assert _status_for(20) == "Critical"
        assert _status_for(0) == "Critical"


class TestAuditResultIntegration:
    """Spot-check that an AuditResult's score lines up with the status mapping."""

    def test_clean_workspace_maps_to_clean(self) -> None:
        now = datetime.now(UTC)
        audit = AuditResult(started_at=now, finished_at=now, findings=[])
        assert _status_for(audit.score) == "Clean"

    def test_critical_finding_drops_to_at_least_warning(self) -> None:
        now = datetime.now(UTC)
        audit = AuditResult(
            started_at=now,
            finished_at=now,
            findings=[Finding(
                check_id="x", severity=Severity.CRITICAL, title="t", detail="d",
            )],
        )
        # Score = 75 → "Warning"
        assert _status_for(audit.score) == "Warning"

    def test_errored_audit_maps_to_incomplete(self) -> None:
        now = datetime.now(UTC)
        audit = AuditResult(
            started_at=now, finished_at=now,
            errors={"public_access": "401 unauthorized"},
        )
        assert _status_for(audit.score) == "Incomplete"
