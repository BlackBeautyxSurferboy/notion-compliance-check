"""Render an AuditResult as a Notion page (header + summary + per-check toggles)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ncc.checks import Severity

if TYPE_CHECKING:
    from ncc.audit import AuditResult
    from ncc.checks import Finding
    from ncc.notion_client import NotionClient


# Notion blocks API caps "children" arrays at 100 entries per request.
_MAX_CHILDREN_PER_REQUEST = 100


def _rich_text(content: str, *, bold: bool = False, code: bool = False) -> dict[str, Any]:
    return {
        "type": "text",
        "text": {"content": content},
        "annotations": {
            "bold": bold,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": code,
            "color": "default",
        },
    }


def _link(content: str, url: str) -> dict[str, Any]:
    return {
        "type": "text",
        "text": {"content": content, "link": {"url": url}},
    }


def _heading(level: int, text: str) -> dict[str, Any]:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_rich_text(text)]}}


def _paragraph(parts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": parts}}


def _callout(text: str, severity: Severity, *, icon: str | None = None) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_rich_text(text)],
            "icon": {"type": "emoji", "emoji": icon or severity.emoji},
            "color": severity.callout_color,
        },
    }


def _bullet(parts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": parts},
    }


def _toggle(title: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {"rich_text": [_rich_text(title, bold=True)], "children": children},
    }


def _divider() -> dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def _finding_blocks(f: Finding) -> list[dict[str, Any]]:
    headline_parts: list[dict[str, Any]] = [_rich_text(f.title, bold=True)]
    if f.page_url:
        headline_parts.append(_rich_text(" — "))
        headline_parts.append(_link("open in Notion", f.page_url))

    blocks: list[dict[str, Any]] = [
        _callout(f.title, f.severity),
        _paragraph(headline_parts),
        _paragraph([_rich_text(f.detail)]),
    ]
    if f.framework_refs:
        refs = " · ".join(f.framework_refs)
        blocks.append(_paragraph([_rich_text(f"Framework: {refs}")]))
    blocks.append(_divider())
    return blocks


def build_report_blocks(result: AuditResult) -> list[dict[str, Any]]:
    """Return the full block list for a compliance report page."""
    blocks: list[dict[str, Any]] = []

    if result.score is None:
        score_severity = Severity.HIGH  # incomplete audit — flag visibly
    elif result.score < 40:
        score_severity = Severity.CRITICAL
    elif result.score < 70:
        score_severity = Severity.HIGH
    elif result.score < 90:
        score_severity = Severity.MEDIUM
    else:
        score_severity = Severity.INFO
    blocks.append(_callout(result.summary_line(), score_severity, icon="📊"))
    blocks.append(_paragraph([_rich_text(
        f"Generated at {result.finished_at.isoformat(timespec='seconds')} "
        f"by Notion Compliance Check (NCC)."
    )]))
    blocks.append(_divider())

    blocks.append(_heading(2, "Severity breakdown"))
    by_sev = result.by_severity
    for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
        count = len(by_sev[sev])
        if count == 0:
            continue
        blocks.append(_bullet([
            _rich_text(f"{sev.emoji} {sev.value.upper()}: ", bold=True),
            _rich_text(f"{count} finding(s)"),
        ]))
    blocks.append(_divider())

    blocks.append(_heading(2, "Findings by check"))
    for check_id, findings in result.by_check.items():
        # Notion caps a single toggle's children at 100. Group findings into safe batches.
        finding_blocks: list[dict[str, Any]] = []
        for f in findings:
            finding_blocks.extend(_finding_blocks(f))
        # Truncate if a single check explodes the toggle past the cap.
        truncated = False
        if len(finding_blocks) > _MAX_CHILDREN_PER_REQUEST - 1:
            finding_blocks = finding_blocks[: _MAX_CHILDREN_PER_REQUEST - 2]
            finding_blocks.append(
                _paragraph([_rich_text(
                    "(further findings truncated — fetch full list via the MCP tool)"
                )])
            )
            truncated = True

        title = f"{check_id} — {len(findings)} finding(s){' (truncated)' if truncated else ''}"
        blocks.append(_toggle(title, finding_blocks))

    if result.errors:
        blocks.append(_divider())
        blocks.append(_heading(2, "Errors during audit"))
        for check_id, msg in result.errors.items():
            blocks.append(_bullet([
                _rich_text(f"{check_id}: ", bold=True),
                _rich_text(msg, code=True),
            ]))

    return blocks


async def write_report(
    client: NotionClient,
    *,
    parent_page_id: str,
    result: AuditResult,
) -> dict[str, Any]:
    """Create a new Notion page under `parent_page_id` containing the full report."""
    score_str = f"{result.score}/100" if result.score is not None else "N/A"
    title = f"Compliance Audit — {result.finished_at.date().isoformat()} ({score_str})"
    body = {
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
        "children": [],
    }
    page = await client.create_page(body)

    blocks = build_report_blocks(result)
    # Append in chunks to stay under the 100-block per-request cap.
    for i in range(0, len(blocks), _MAX_CHILDREN_PER_REQUEST):
        chunk = blocks[i : i + _MAX_CHILDREN_PER_REQUEST]
        await client.append_block_children(page["id"], chunk)
    return page
