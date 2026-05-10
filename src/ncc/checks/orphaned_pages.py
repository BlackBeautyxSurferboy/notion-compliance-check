"""Find pages in databases that have no assigned owner — accountability gap."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ncc.checks.base import Check, Finding, Severity
from ncc.notion_client import page_title, page_url

if TYPE_CHECKING:
    from ncc.notion_client import NotionClient


OWNER_PROPERTY_NAMES = {
    "owner", "verantwortlich", "verantwortliche", "verantwortlicher",
    "responsible", "assignee", "zuständig", "lead", "ansprechpartner",
}


def _people_property_is_empty(prop: dict[str, Any]) -> bool:
    if prop.get("type") != "people":
        return False
    return len(prop.get("people", [])) == 0


class OrphanedPagesCheck(Check):
    id = "orphaned_pages"
    name = "Orphaned Pages (No Owner)"
    description = (
        "In every database that has an Owner-style People property, flags pages where "
        "that property is empty. Accountability is a foundational ISO 27001 requirement "
        "(A.5.2 — Information security roles and responsibilities)."
    )

    async def run(self, client: NotionClient) -> list[Finding]:
        findings: list[Finding] = []
        async for db in client.search(filter_object="database"):
            db_id = db.get("id")
            if not db_id:
                continue

            owner_prop_name = self._find_owner_property(db.get("properties", {}))
            if not owner_prop_name:
                continue

            db_title = self._database_title(db)

            async for page in client.query_database(db_id):
                props = page.get("properties", {})
                owner = props.get(owner_prop_name, {})
                if not _people_property_is_empty(owner):
                    continue

                title = page_title(page)
                findings.append(
                    Finding(
                        check_id=self.id,
                        severity=Severity.MEDIUM,
                        title=f"No owner: {title}",
                        detail=(
                            f"Page in database '{db_title}' has an empty "
                            f"'{owner_prop_name}' property. Assign someone responsible."
                        ),
                        page_id=page.get("id"),
                        page_url=page_url(page),
                        page_title=title,
                        framework_refs=["ISO 27001 A.5.2", "SOC 2 CC1.3"],
                    )
                )
        return findings

    @staticmethod
    def _find_owner_property(properties: dict[str, Any]) -> str | None:
        for name, prop in properties.items():
            if prop.get("type") != "people":
                continue
            if name.strip().lower() in OWNER_PROPERTY_NAMES:
                return name
        return None

    @staticmethod
    def _database_title(db: dict[str, Any]) -> str:
        parts = db.get("title", [])
        return "".join(p.get("plain_text", "") for p in parts) or "(untitled)"
