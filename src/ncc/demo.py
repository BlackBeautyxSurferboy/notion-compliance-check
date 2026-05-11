"""Spin up (and tear down) a demo workspace with deliberately problematic content.

This exists so a reviewer or interviewer can clone the repo, run one command,
and immediately have audit-triggering content in their workspace — without
copy-pasting Markdown into pages by hand.

Every page and database created here has the prefix `[NCC Demo]` in its title.
That prefix is how `teardown_demo_workspace` finds them again later, so a fresh
checkout from any machine can clean up the demo state without needing a local
state file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ncc.notion_client import NotionClient


DEMO_PREFIX = "[NCC Demo]"


@dataclass
class DemoArtifacts:
    """IDs of the things we just created. Returned for the caller to display."""

    sandbox_page_id: str
    sandbox_page_url: str
    public_page_id: str
    public_page_url: str
    risk_db_id: str
    risk_db_url: str


# -----------------------------------------------------------------------------
# Block-builder helpers (shared with report.py shape, kept local to keep demo
# content self-contained).
# -----------------------------------------------------------------------------


def _rich(content: str, *, bold: bool = False) -> dict[str, Any]:
    return {
        "type": "text",
        "text": {"content": content},
        "annotations": {
            "bold": bold,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default",
        },
    }


def _h(level: int, text: str) -> dict[str, Any]:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_rich(text)]}}


def _p(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [_rich(text)]}}


def _bullet(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_rich(text)]},
    }


def _code(text: str, language: str = "bash") -> dict[str, Any]:
    return {
        "object": "block",
        "type": "code",
        "code": {"rich_text": [_rich(text)], "language": language},
    }


def _callout(text: str, *, emoji: str = "⚠", color: str = "yellow_background") -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_rich(text)],
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    }


# -----------------------------------------------------------------------------
# Demo content — deliberately problematic. All PII values are public test data.
# -----------------------------------------------------------------------------


def _sandbox_blocks() -> list[dict[str, Any]]:
    return [
        _callout(
            "Demo-Page für NCC. Alle Werte sind öffentliche Test-Daten ohne reale "
            "Funktion. Wird beim `ncc demo-teardown` wieder entfernt.",
            emoji="🧪",
            color="gray_background",
        ),
        _h(2, "Onboarding neuer Mitarbeitende"),
        _bullet("Begrüßungsmail rausschicken"),
        _bullet("Hardware-Bestellung freigeben (MacBook Pro, externer Monitor)"),
        _bullet("Slack- und Notion-Zugänge anlegen"),
        _bullet(
            "Vertragsdaten ans Lohnbüro: Überweisung an die Test-IBAN "
            "DE89 3704 0044 0532 0130 00 (Bank: Commerzbank Berlin)"
        ),
        _bullet(
            "Steuerliche Daten: Steuer-ID des Mitarbeiters muss übermittelt werden — "
            "bei letztem Onboarding war das 12345678901"
        ),
        _bullet("Schulungsunterlagen verschicken"),
        _h(2, "Reisekostenerstattung — Q2"),
        _p(
            "Für Vorabbuchungen bitte die folgende Firmenkarte verwenden. Anfrage und "
            "Originalbelege gehen anschließend an die Buchhaltung."
        ),
        _bullet("Karteninhaber: Acme GmbH Reisekonto"),
        _bullet("Kartennummer: 4539 1488 0343 6467"),
        _bullet("Gültig bis: 12 / 2027, CVC: 123"),
        _bullet("Verfügungsrahmen: 5.000 € pro Reise"),
        _p(
            "Bei Auslandsreisen nach UK bitte stattdessen das UK-Konto nutzen: "
            "GB82 WEST 1234 5698 7654 32."
        ),
        _h(2, "Deploy-Runbook (Staging)"),
        _p("Quick-Reference für den Notfall — falls niemand aus DevOps erreichbar ist."),
        _code(
            "ssh deploy@staging.acme.example\n"
            "cd /var/www/app\n"
            "export DB_USER=admin\n"
            "export DB_PASSWORD=hunter2_supersecret\n"
            "export PAYMENT_API_KEY=demo_FAKE_KEY_NOT_REAL_abc123XYZdef\n"
            "./deploy.sh --env=staging"
        ),
        _callout(
            "Bitte das hier nicht in Slack rumschicken. (Genau deshalb checkt NCC sowas.)",
            emoji="🚨",
            color="red_background",
        ),
        _h(2, "Kunden-Notizen — Schmidt Industries GmbH"),
        _p(
            "Hauptansprechpartner ist Markus Schmidt, Geschäftsführer. Persönliche "
            "Steuer-ID 23456789012 (für die Erstattung des letzten Quartals — bitte "
            "nicht weiterleiten). Bezahlung läuft über die IBAN "
            "FR14 2004 1010 0505 0001 3M02 606."
        ),
        _p(
            "Notiz: Markus hat im letzten Call angedeutet, dass sein Vater (Inhaber) "
            "die Firma in 2027 verkaufen will — vertraulich behandeln."
        ),
        _h(2, "Offene Punkte / TODO"),
        _bullet("Datenschutzerklärung an die neue DSGVO-Auslegung anpassen"),
        _bullet("Passwort-Policy review — der Approach mit Klartext ist nicht skalierbar"),
        _bullet("Diese Sandbox-Page nach der Demo aufräumen (oder `ncc demo-teardown`) 🙄"),
    ]


def _public_page_blocks() -> list[dict[str, Any]]:
    return [
        _callout(
            "Demo-Page für NCC. Bitte manuell auf 'Im Web veröffentlichen' setzen, "
            "damit der Public-Access-Check anschlägt — die Notion-API darf das nicht "
            "automatisch tun.",
            emoji="🌍",
            color="orange_background",
        ),
        _h(2, "Q3 2026 — Finanzkennzahlen"),
        _p("Umsatzziel: 4,2 Mio. €. Bisher erreicht: 3,1 Mio. €. Gap: 1,1 Mio. €."),
        _p(
            "Strategische Übernahme-Diskussion mit Acme Corp aktuell auf Eis — der "
            "Asking Price liegt bei 12-14x ARR. Wird nochmal im November bewertet."
        ),
        _bullet("Q3-Forecast: 4,0 Mio. €"),
        _bullet("Personalplanung: 3 Senior Hires Engineering, 1 Lead Sales"),
        _bullet("Risiken: Cloudflare-Migration verzögert (vermutlich Q4)"),
    ]


def _risk_db_properties() -> dict[str, Any]:
    return {
        "Name": {"title": {}},
        "Verantwortlich": {"people": {}},
        "Risiko-Level": {
            "select": {
                "options": [
                    {"name": "Low", "color": "green"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "High", "color": "red"},
                ]
            }
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "Offen", "color": "red"},
                    {"name": "In Bearbeitung", "color": "yellow"},
                    {"name": "Mitigiert", "color": "green"},
                ]
            }
        },
        "Notizen": {"rich_text": {}},
    }


async def _seed_risk_db(
    client: NotionClient, db_id: str, owner_user_id: str | None
) -> None:
    """Add three example rows. One deliberately has no owner (the orphan trigger)."""

    def _row(name: str, level: str, status: str, notes: str, *, with_owner: bool) -> dict[str, Any]:
        props: dict[str, Any] = {
            "Name": {"title": [{"type": "text", "text": {"content": name}}]},
            "Risiko-Level": {"select": {"name": level}},
            "Status": {"select": {"name": status}},
            "Notizen": {
                "rich_text": [{"type": "text", "text": {"content": notes}}]
            },
        }
        if with_owner and owner_user_id is not None:
            props["Verantwortlich"] = {"people": [{"id": owner_user_id}]}
        return {"parent": {"database_id": db_id}, "properties": props}

    rows = [
        _row(
            "Datenleck-Notfallplan überarbeiten",
            "High", "Offen",
            "Aktuelle Version aus 2024 — Kontaktpfade veraltet.",
            with_owner=True,
        ),
        _row(
            "DSGVO-Auskunftsersuchen-Prozess dokumentieren",
            "Medium", "In Bearbeitung",
            "Template steht, Process-Doku fehlt.",
            with_owner=True,
        ),
        _row(
            "Dienstleister-Audit Cloudflare (AVV)",
            "Medium", "Offen",
            "Vertrag seit 2023 in Kraft, AVV fehlt formell.",
            with_owner=False,   # <-- orphaned trigger
        ),
    ]
    for body in rows:
        await client.create_page(body)


async def _whoami(client: NotionClient) -> str | None:
    """Best-effort lookup of the bot's user ID — for the risk-db owner field.

    Notion integrations have a user-record themselves, but their type is 'bot'
    and you cannot assign a People property to a bot. We need a *person*, so we
    fall back to the first human user the integration can see, which should be
    the workspace owner when running locally.
    """
    try:
        # Reaching into _request because /users isn't part of the public client surface
        # but we only need it transiently for owner-id discovery during demo seeding.
        data = await client._request("GET", "/users")
    except Exception:
        return None
    for user in data.get("results", []):
        if user.get("type") == "person":
            return user.get("id")
    return None


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


async def setup_demo_workspace(
    client: NotionClient,
    *,
    parent_page_id: str,
) -> DemoArtifacts:
    """Create the three demo containers under `parent_page_id`.

    All artifacts get the `[NCC Demo]` prefix in their title so teardown can find
    them again. The parent page must already be connected to the integration —
    we cannot grant access through the API.

    Note: Public-web sharing for the public page must be enabled manually after
    creation (the integration capability does not include 'manage sharing').
    """

    # 1. Sandbox page with PII content
    sandbox = await client.create_page({
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {"title": [
                {"type": "text", "text": {"content": f"{DEMO_PREFIX} Test-Sandbox"}}
            ]}
        },
        "children": _sandbox_blocks(),
    })

    # 2. Page with sensitive title (needs manual public-web-share to trigger CRITICAL)
    public = await client.create_page({
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {"title": [
                {"type": "text", "text": {
                    "content": f"{DEMO_PREFIX} Q3 Finanzen — vertraulich"
                }}
            ]}
        },
        "children": _public_page_blocks(),
    })

    # 3. Database with owner column + one orphaned row
    risk_db = await client.create_database({
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": f"{DEMO_PREFIX} Risiko-Register"}}],
        "properties": _risk_db_properties(),
    })
    owner_user_id = await _whoami(client)
    await _seed_risk_db(client, risk_db["id"], owner_user_id)

    return DemoArtifacts(
        sandbox_page_id=sandbox["id"],
        sandbox_page_url=sandbox.get("url", ""),
        public_page_id=public["id"],
        public_page_url=public.get("url", ""),
        risk_db_id=risk_db["id"],
        risk_db_url=risk_db.get("url", ""),
    )


async def teardown_demo_workspace(client: NotionClient) -> int:
    """Archive every page and database whose title starts with `[NCC Demo]`.

    Returns the number of artifacts archived. Archive is a soft-delete in Notion;
    items go to the trash and are recoverable from the UI for 30 days.
    """
    archived = 0

    async for item in client.search():
        title = _extract_title(item)
        if not title.startswith(DEMO_PREFIX):
            continue
        try:
            if item.get("object") == "database":
                await client.archive_database(item["id"])
            else:
                await client.archive_page(item["id"])
            archived += 1
        except Exception:
            # One stuck archive shouldn't block the rest.
            continue
    return archived


def _extract_title(item: dict[str, Any]) -> str:
    """Generic title extraction that works for both pages and databases."""
    obj = item.get("object")
    if obj == "database":
        parts = item.get("title", [])
        return "".join(p.get("plain_text", "") for p in parts)
    # Page: look for a title property
    for prop in item.get("properties", {}).values():
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts)
    return ""
