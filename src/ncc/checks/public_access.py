"""Detect pages exposed to the public web — the single highest-impact compliance risk."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ncc.checks.base import Check, Finding, Severity
from ncc.notion_client import page_title, page_url

if TYPE_CHECKING:
    from ncc.notion_client import NotionClient


SENSITIVE_KEYWORDS = [
    # Financial
    "financ", "salary", "compensation", "budget", "revenue", "invoice",
    "gehalt", "umsatz", "rechnung", "lohn",
    # Credentials / secrets
    "password", "passwort", "secret", "credential", "api key", "token",
    "ssh", "private key",
    # HR / personnel
    "hr ", "personnel", "performance review", "termination",
    "personal", "kündigung", "abmahnung", "mitarbeitergespräch",
    # Legal / strategy
    "confidential", "vertraulich", "nda", "legal", "strategy",
    "m&a", "acquisition", "merger",
    # Customer / PII
    "customer list", "kundenliste", "client data", "kundendaten",
]
_SENSITIVE_RE = re.compile("|".join(re.escape(k) for k in SENSITIVE_KEYWORDS), re.IGNORECASE)


class PublicAccessCheck(Check):
    id = "public_access"
    name = "Public Web Exposure"
    description = (
        "Flags pages that are shared to the public web — critical for DSGVO Art. 32 "
        "(security of processing) and SOC 2 CC6.1 (logical access controls)."
    )

    async def run(self, client: NotionClient) -> list[Finding]:
        findings: list[Finding] = []
        async for item in client.search(filter_object="page"):
            public_url = item.get("public_url")
            if not public_url:
                continue

            title = page_title(item)
            sensitive_match = _SENSITIVE_RE.search(title)

            if sensitive_match:
                severity = Severity.CRITICAL
                detail = (
                    f"Page is publicly accessible AND its title contains the sensitive "
                    f"keyword '{sensitive_match.group(0)}'. Anyone with the link can read it."
                )
                refs = ["DSGVO Art. 32", "DSGVO Art. 5(1)(f)", "SOC 2 CC6.1", "ISO 27001 A.5.10"]
            else:
                severity = Severity.HIGH
                detail = (
                    "Page is publicly accessible. Even if the title looks harmless, "
                    "review its content and confirm the public exposure is intentional."
                )
                refs = ["DSGVO Art. 32", "SOC 2 CC6.1"]

            findings.append(
                Finding(
                    check_id=self.id,
                    severity=severity,
                    title=f"Public page: {title}",
                    detail=detail,
                    page_id=item.get("id"),
                    page_url=page_url(item),
                    page_title=title,
                    framework_refs=refs,
                )
            )
        return findings
