"""Compliance dashboard — a Notion page that shows live audit posture.

The dashboard consists of:
- A header page with description, score callout, and embedded history DB view
- A history database with one row per audit run (date, score, severity counts)

Once set up, every `ncc audit --post` adds a new row to the history DB. The
dashboard's chart view then trends the score over time — purely with Notion
primitives, no external visualization layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ncc.checks import Severity

if TYPE_CHECKING:
    from ncc.audit import AuditResult
    from ncc.notion_client import NotionClient


DASHBOARD_PREFIX = "[NCC]"


@dataclass
class DashboardArtifacts:
    dashboard_page_id: str
    dashboard_page_url: str
    history_db_id: str
    history_db_url: str


# -----------------------------------------------------------------------------
# Block helpers (kept local — mirrors report.py shape)
# -----------------------------------------------------------------------------


def _rich(content: str, *, bold: bool = False, code: bool = False) -> dict[str, Any]:
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


def _h(level: int, text: str) -> dict[str, Any]:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_rich(text, bold=True)]}}


def _p(parts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": parts}}


def _callout(text: str, *, emoji: str, color: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_rich(text)],
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    }


def _divider() -> dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def _link_to_db(db_id: str) -> dict[str, Any]:
    """Inline-reference to a database — Notion renders it as a clickable view."""
    return {
        "object": "block",
        "type": "link_to_page",
        "link_to_page": {"type": "database_id", "database_id": db_id},
    }


# -----------------------------------------------------------------------------
# History database schema
# -----------------------------------------------------------------------------


def _history_db_properties() -> dict[str, Any]:
    return {
        "Run": {"title": {}},
        "Datum": {"date": {}},
        "Score": {"number": {"format": "number"}},
        "Status": {
            "select": {
                "options": [
                    {"name": "Clean", "color": "green"},
                    {"name": "Warning", "color": "yellow"},
                    {"name": "Risk", "color": "orange"},
                    {"name": "Critical", "color": "red"},
                    {"name": "Incomplete", "color": "gray"},
                ]
            }
        },
        "Critical": {"number": {"format": "number"}},
        "High": {"number": {"format": "number"}},
        "Medium": {"number": {"format": "number"}},
        "Low": {"number": {"format": "number"}},
        "Dauer (s)": {"number": {"format": "number_with_commas"}},
        "Report-Page": {"url": {}},
        "Notiz": {"rich_text": {}},
    }


def _status_for(score: int | None) -> str:
    if score is None:
        return "Incomplete"
    if score >= 90:
        return "Clean"
    if score >= 70:
        return "Warning"
    if score >= 40:
        return "Risk"
    return "Critical"


# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------


async def setup_dashboard(
    client: NotionClient,
    *,
    parent_page_id: str,
) -> DashboardArtifacts:
    """Create the dashboard page and the history database underneath it.

    Layout strategy:
        Dashboard Page
          ├─ Hero callout
          ├─ How-to paragraph
          ├─ History Database (created as child of the dashboard page)
          └─ Footer divider + links
    """

    # 1. Create the dashboard page (empty for now — we'll fill it after we
    #    have the history DB ID so we can link to it).
    dashboard = await client.create_page({
        "parent": {"page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": "🛡"},
        "properties": {
            "title": {"title": [
                {"type": "text", "text": {
                    "content": f"{DASHBOARD_PREFIX} Compliance Dashboard"
                }}
            ]}
        },
    })
    dashboard_id = dashboard["id"]

    # 2. Create the history database as a child of the dashboard page.
    history_db = await client.create_database({
        "parent": {"type": "page_id", "page_id": dashboard_id},
        "icon": {"type": "emoji", "emoji": "📈"},
        "title": [{"type": "text", "text": {
            "content": f"{DASHBOARD_PREFIX} Audit-Historie"
        }}],
        "properties": _history_db_properties(),
    })
    history_db_id = history_db["id"]

    # 3. Fill the dashboard page with intro content. The DB is already a child
    #    of the dashboard, so it shows up inline above this content automatically.
    blocks = [
        _callout(
            "Live-Dashboard für deine Notion-Compliance. Jeder Audit-Run "
            "ergänzt eine Zeile in der Historie unten. Tipps & Setup unter dem "
            "Trennstrich.",
            emoji="🛡",
            color="blue_background",
        ),
        _h(2, "So funktioniert's"),
        _p([_rich(
            "Triggere einen Audit auf einem der drei Wege: über den Notion-Button "
            "(siehe unten), per CLI mit "
        ), _rich("ncc audit --post", code=True), _rich(
            ", oder über Notion AI / Claude (NCC ist ein MCP-Server). Bei jedem "
            "Run wird automatisch eine Zeile in die Historie geschrieben — Score, "
            "Schweregrad-Zählungen, Link zur Report-Page."
        )]),
        _h(2, "Was wird geprüft"),
        _p([_rich(
            "Vier Checks, jeweils an eine konkrete Norm verankert: Public Web "
            "Exposure (DSGVO Art. 32), Orphaned Pages ohne Owner (ISO 27001 "
            "A.5.2), Stale Data (DSGVO Art. 5(1)(d)) und Plaintext-PII mit Luhn-"
            "und mod-97-Validatoren (PCI-DSS Req 3.4, DSGVO Art. 9)."
        )]),
        _divider(),
        _h(3, "Setup: Audit-Button"),
        _p([_rich(
            "Tippe "
        ), _rich("/button", code=True), _rich(
            " in einer Page deiner Wahl, gib ihm das Label "
        ), _rich("🔍 Compliance-Audit starten", bold=True), _rich(
            ", füge eine "
        ), _rich("Webhook senden", bold=True), _rich(
            "-Aktion hinzu, URL = deine NCC-Deploy-URL + "
        ), _rich("/webhook/run-audit", code=True), _rich(
            ", JSON-Body = "
        ), _rich('{"secret": "<dein-NCC_WEBHOOK_SECRET>"}', code=True), _rich(
            ". Speichern. Fertig."
        )]),
        _h(3, "Repo"),
        _p([_rich(
            "Code, Tests, Architektur-Diagramm und Build-Story: "
        ), {
            "type": "text",
            "text": {
                "content": "github.com/BlackBeautyxSurferboy/notion-compliance-check",
                "link": {"url": "https://github.com/BlackBeautyxSurferboy/notion-compliance-check"},
            },
        }]),
    ]
    await client.append_block_children(dashboard_id, blocks)

    return DashboardArtifacts(
        dashboard_page_id=dashboard_id,
        dashboard_page_url=dashboard.get("url", ""),
        history_db_id=history_db_id,
        history_db_url=history_db.get("url", ""),
    )


# -----------------------------------------------------------------------------
# Write a single audit run into the history DB
# -----------------------------------------------------------------------------


async def write_audit_to_history(
    client: NotionClient,
    *,
    history_db_id: str,
    result: AuditResult,
    report_page_url: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Add one row to the history DB for this audit run."""
    counts = {sev: len(result.by_severity[sev]) for sev in Severity}
    score = result.score
    status = _status_for(score)
    timestamp = result.finished_at.astimezone(UTC).isoformat()
    run_title = f"Audit {result.finished_at.strftime('%Y-%m-%d %H:%M')}"

    props: dict[str, Any] = {
        "Run": {"title": [{"type": "text", "text": {"content": run_title}}]},
        "Datum": {"date": {"start": timestamp}},
        "Status": {"select": {"name": status}},
        "Critical": {"number": counts[Severity.CRITICAL]},
        "High": {"number": counts[Severity.HIGH]},
        "Medium": {"number": counts[Severity.MEDIUM]},
        "Low": {"number": counts[Severity.LOW]},
        "Dauer (s)": {"number": round(result.duration_seconds, 2)},
    }
    if score is not None:
        props["Score"] = {"number": score}
    if report_page_url:
        props["Report-Page"] = {"url": report_page_url}
    if note:
        props["Notiz"] = {"rich_text": [{"type": "text", "text": {"content": note}}]}

    return await client.create_page({
        "parent": {"database_id": history_db_id},
        "properties": props,
    })


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
