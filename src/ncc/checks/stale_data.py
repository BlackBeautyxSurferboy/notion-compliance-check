"""Flag pages that have not been touched for a long time — likely outdated information."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ncc.checks.base import Check, Finding, Severity
from ncc.notion_client import page_title, page_url

if TYPE_CHECKING:
    from ncc.notion_client import NotionClient


class StaleDataCheck(Check):
    id = "stale_data"
    name = "Stale Pages"
    description = (
        "Pages not edited for a long time often contain outdated information. "
        "DSGVO Art. 5(1)(d) — accuracy — requires that personal data be kept up to date; "
        "stale documents are also an ISO 27001 A.5.34 concern (privacy and protection of PII)."
    )

    def __init__(self, threshold_days: int | None = None) -> None:
        if threshold_days is None:
            threshold_days = int(os.environ.get("NCC_STALE_THRESHOLD_DAYS", "365"))
        self.threshold_days = threshold_days

    async def run(self, client: NotionClient) -> list[Finding]:
        cutoff = datetime.now(UTC) - timedelta(days=self.threshold_days)
        findings: list[Finding] = []

        async for item in client.search(filter_object="page"):
            edited = item.get("last_edited_time")
            if not edited:
                continue
            edited_dt = datetime.fromisoformat(edited.replace("Z", "+00:00"))
            if edited_dt >= cutoff:
                continue

            age_days = (datetime.now(UTC) - edited_dt).days
            severity = Severity.LOW if age_days < 730 else Severity.MEDIUM
            title = page_title(item)

            findings.append(
                Finding(
                    check_id=self.id,
                    severity=severity,
                    title=f"Stale ({age_days}d): {title}",
                    detail=(
                        f"Page last edited {age_days} days ago "
                        f"({edited_dt.date().isoformat()}). Threshold is "
                        f"{self.threshold_days} days. Review, update, or archive."
                    ),
                    page_id=item.get("id"),
                    page_url=page_url(item),
                    page_title=title,
                    framework_refs=["DSGVO Art. 5(1)(d)", "ISO 27001 A.5.34"],
                )
            )
        return findings
