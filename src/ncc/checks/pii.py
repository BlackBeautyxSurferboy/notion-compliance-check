"""Scan page content for personally identifiable information in plain text.

This is a deliberately conservative scan — false positives are far less harmful
than false negatives in a compliance context, but we still validate structurally
(e.g. Luhn for credit cards, IBAN checksum) to keep noise manageable.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ncc.checks.base import Check, Finding, Severity
from ncc.notion_client import page_title, page_url

if TYPE_CHECKING:
    from ncc.notion_client import NotionClient


@dataclass(frozen=True, slots=True)
class PIIPattern:
    name: str
    regex: re.Pattern[str]
    severity: Severity
    framework_refs: tuple[str, ...]
    validator: str | None = None  # name of an extra structural check


# German tax ID: 11 digits with checksum (we only do shape-match — full validator is overkill).
PII_PATTERNS: list[PIIPattern] = [
    PIIPattern(
        name="credit_card",
        regex=re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
        severity=Severity.CRITICAL,
        framework_refs=("PCI-DSS Req 3.4", "DSGVO Art. 9", "DSGVO Art. 32"),
        validator="luhn",
    ),
    PIIPattern(
        # IBANs are commonly written in 4-char groups separated by spaces;
        # the optional space-or-nothing between chars is what makes this match
        # both "DE89370400440532013000" and "DE89 3704 0044 0532 0130 00".
        name="iban",
        regex=re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,38}\b"),
        severity=Severity.HIGH,
        framework_refs=("DSGVO Art. 32",),
        validator="iban",
    ),
    PIIPattern(
        name="german_tax_id",
        regex=re.compile(r"(?<!\d)\d{11}(?!\d)"),
        severity=Severity.HIGH,
        framework_refs=("DSGVO Art. 9", "AO §139b"),
    ),
    PIIPattern(
        name="german_social_security",
        regex=re.compile(r"\b\d{2}\s?\d{6}\s?[A-Z]\s?\d{3}\b"),
        severity=Severity.HIGH,
        framework_refs=("DSGVO Art. 9",),
    ),
    PIIPattern(
        name="us_ssn",
        regex=re.compile(r"\b(?!000|666)(?!9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
        severity=Severity.HIGH,
        framework_refs=("DSGVO Art. 9", "GLBA"),
    ),
    PIIPattern(
        name="email_with_password_context",
        regex=re.compile(
            r"(?i)password\s*[:=]\s*\S+|passwort\s*[:=]\s*\S+|api[_-]?key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"
        ),
        severity=Severity.CRITICAL,
        framework_refs=("DSGVO Art. 32", "ISO 27001 A.5.17"),
    ),
]


def _luhn_valid(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if len(nums) < 13:
        return False
    # Real card numbers never start with 0 (issuer identification number rules)
    # and never consist of a single repeated digit — without this guard,
    # "0000…" passes Luhn arithmetically but is obviously not a real card.
    if nums[0] == 0 or len(set(nums)) == 1:
        return False
    checksum = 0
    parity = len(nums) % 2
    for i, n in enumerate(nums):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        checksum += n
    return checksum % 10 == 0


def _iban_valid(value: str) -> bool:
    iban = re.sub(r"\s+", "", value).upper()
    if len(iban) < 15 or len(iban) > 34:
        return False
    rearranged = iban[4:] + iban[:4]
    converted = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    try:
        return int(converted) % 97 == 1
    except ValueError:
        return False


VALIDATORS = {"luhn": _luhn_valid, "iban": _iban_valid}


def find_pii(text: str) -> list[tuple[PIIPattern, str]]:
    """Return (pattern, matched_string) for every PII match in `text`."""
    matches: list[tuple[PIIPattern, str]] = []
    for pattern in PII_PATTERNS:
        for match in pattern.regex.finditer(text):
            value = match.group(0)
            if pattern.validator:
                validator = VALIDATORS.get(pattern.validator)
                if validator and not validator(value):
                    continue
            matches.append((pattern, value))
    return matches


def _extract_text_from_block(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    if not block_type:
        return ""
    payload = block.get(block_type, {})
    rich = payload.get("rich_text") or payload.get("text") or []
    return "".join(r.get("plain_text", "") for r in rich if isinstance(r, dict))


def _redact(value: str, *, keep: int = 4) -> str:
    cleaned = re.sub(r"\s+", "", value)
    if len(cleaned) <= keep:
        return "*" * len(cleaned)
    return cleaned[:keep] + "*" * (len(cleaned) - keep)


class PIIExposureCheck(Check):
    id = "pii_exposure"
    name = "PII in Page Content"
    description = (
        "Scans page bodies for plaintext PII patterns: credit card numbers (Luhn-validated), "
        "IBANs (mod-97-validated), German tax IDs and social security numbers, US SSNs, and "
        "embedded passwords / API keys. Anchored to DSGVO Art. 9, Art. 32, and PCI-DSS Req 3.4."
    )

    def __init__(self, *, max_concurrent: int = 5) -> None:
        self.max_concurrent = max_concurrent

    async def run(self, client: NotionClient) -> list[Finding]:
        pages: list[dict[str, Any]] = []
        async for item in client.search(filter_object="page"):
            pages.append(item)

        sem = asyncio.Semaphore(self.max_concurrent)

        async def scan_page(page: dict[str, Any]) -> list[Finding]:
            async with sem:
                return await self._scan_one(client, page)

        results = await asyncio.gather(*(scan_page(p) for p in pages))
        return [f for sub in results for f in sub]

    async def _scan_one(
        self, client: NotionClient, page: dict[str, Any]
    ) -> list[Finding]:
        page_id = page.get("id")
        if not page_id:
            return []

        title = page_title(page)
        url = page_url(page)
        text_chunks: list[str] = []
        try:
            async for block in client.retrieve_block_children(page_id):
                chunk = _extract_text_from_block(block)
                if chunk:
                    text_chunks.append(chunk)
        except Exception:
            # Never fail the whole audit on one bad page (e.g. block we can't read).
            return []

        text = "\n".join(text_chunks)
        if not text:
            return []

        matches = find_pii(text)
        if not matches:
            return []

        # Group matches per pattern for cleaner reporting.
        by_pattern: dict[str, list[str]] = {}
        severities: dict[str, Severity] = {}
        refs: dict[str, tuple[str, ...]] = {}
        for pattern, value in matches:
            by_pattern.setdefault(pattern.name, []).append(_redact(value))
            severities[pattern.name] = pattern.severity
            refs[pattern.name] = pattern.framework_refs

        findings: list[Finding] = []
        for pattern_name, values in by_pattern.items():
            preview = ", ".join(values[:3])
            extra = f" (+{len(values) - 3} more)" if len(values) > 3 else ""
            findings.append(
                Finding(
                    check_id=self.id,
                    severity=severities[pattern_name],
                    title=f"PII ({pattern_name}): {title}",
                    detail=(
                        f"Found {len(values)} match(es) of pattern '{pattern_name}' "
                        f"in page content. Redacted preview: {preview}{extra}"
                    ),
                    page_id=page_id,
                    page_url=url,
                    page_title=title,
                    framework_refs=list(refs[pattern_name]),
                )
            )
        return findings
