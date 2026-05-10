"""Run all (or a subset of) compliance checks and aggregate findings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ncc.checks import ALL_CHECKS, Check, Finding, Severity

if TYPE_CHECKING:
    from ncc.notion_client import NotionClient


_SEVERITY_WEIGHT = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 10,
    Severity.MEDIUM: 4,
    Severity.LOW: 1,
    Severity.INFO: 0,
}


@dataclass(slots=True)
class AuditResult:
    started_at: datetime
    finished_at: datetime
    findings: list[Finding] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def by_severity(self) -> dict[Severity, list[Finding]]:
        out: dict[Severity, list[Finding]] = {s: [] for s in Severity}
        for f in self.findings:
            out[f.severity].append(f)
        return out

    @property
    def by_check(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.check_id, []).append(f)
        return out

    @property
    def score(self) -> int:
        """0–100 compliance score. 100 means clean, 0 means critical findings dominate."""
        penalty = sum(_SEVERITY_WEIGHT[f.severity] for f in self.findings)
        return max(0, 100 - min(penalty, 100))

    def summary_line(self) -> str:
        counts = {s: len(self.by_severity[s]) for s in Severity}
        return (
            f"Score {self.score}/100 — "
            f"{counts[Severity.CRITICAL]} critical, "
            f"{counts[Severity.HIGH]} high, "
            f"{counts[Severity.MEDIUM]} medium, "
            f"{counts[Severity.LOW]} low "
            f"(took {self.duration_seconds:.1f}s)"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "score": self.score,
            "findings": [f.to_dict() for f in self.findings],
            "errors": self.errors,
        }


async def run_audit(
    client: NotionClient,
    *,
    checks: list[Check] | None = None,
) -> AuditResult:
    if checks is None:
        checks = [cls() for cls in ALL_CHECKS]

    started = datetime.now(UTC)
    results = await asyncio.gather(
        *(c.run(client) for c in checks), return_exceptions=True
    )
    finished = datetime.now(UTC)

    audit = AuditResult(started_at=started, finished_at=finished)
    for check, result in zip(checks, results, strict=True):
        if isinstance(result, BaseException):
            audit.errors[check.id] = f"{type(result).__name__}: {result}"
        else:
            audit.findings.extend(result)

    audit.findings.sort(
        key=lambda f: (-_SEVERITY_WEIGHT[f.severity], f.check_id, f.title)
    )
    return audit
