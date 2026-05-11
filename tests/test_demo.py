"""Tests for the demo module — block construction + title detection.

We don't mock the full Notion API here; setup/teardown require live calls and
are covered by manual demo runs. These tests pin down the pure-function pieces
that are easy to break unnoticed."""

from __future__ import annotations

from ncc.demo import (
    DEMO_PREFIX,
    _extract_title,
    _public_page_blocks,
    _risk_db_properties,
    _sandbox_blocks,
)


class TestSandboxBlocks:
    def test_contains_at_least_one_credit_card_block(self) -> None:
        blocks = _sandbox_blocks()
        text = " ".join(_collect_text(b) for b in blocks)
        # Visa test number
        assert "4539 1488 0343 6467" in text

    def test_contains_iban_in_text(self) -> None:
        text = " ".join(_collect_text(b) for b in _sandbox_blocks())
        assert "DE89 3704 0044 0532 0130 00" in text
        assert "GB82 WEST 1234 5698 7654 32" in text

    def test_contains_password_assignment(self) -> None:
        text = " ".join(_collect_text(b) for b in _sandbox_blocks())
        assert "DB_PASSWORD=hunter2_supersecret" in text

    def test_contains_german_tax_id(self) -> None:
        text = " ".join(_collect_text(b) for b in _sandbox_blocks())
        assert "12345678901" in text


class TestPublicPageBlocks:
    def test_contains_sensitive_keyword_in_content(self) -> None:
        text = " ".join(_collect_text(b) for b in _public_page_blocks())
        assert "Acme Corp" in text or "Übernahme" in text


class TestRiskDBSchema:
    def test_required_columns_present(self) -> None:
        props = _risk_db_properties()
        for name in ("Name", "Verantwortlich", "Risiko-Level", "Status", "Notizen"):
            assert name in props, f"missing column: {name}"

    def test_owner_column_is_people_type(self) -> None:
        props = _risk_db_properties()
        assert "people" in props["Verantwortlich"]


class TestTitleExtraction:
    def test_page_with_demo_prefix(self) -> None:
        page = {
            "object": "page",
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"plain_text": f"{DEMO_PREFIX} Test-Sandbox"}],
                }
            },
        }
        assert _extract_title(page).startswith(DEMO_PREFIX)

    def test_database_with_demo_prefix(self) -> None:
        db = {
            "object": "database",
            "title": [{"plain_text": f"{DEMO_PREFIX} Risiko-Register"}],
        }
        assert _extract_title(db).startswith(DEMO_PREFIX)

    def test_missing_title_returns_empty_string(self) -> None:
        assert _extract_title({"object": "page", "properties": {}}) == ""


def _collect_text(block: dict) -> str:
    block_type = block.get("type")
    if not block_type:
        return ""
    payload = block.get(block_type, {})
    parts = payload.get("rich_text", [])
    return " ".join(
        part.get("text", {}).get("content", "")
        for part in parts
        if isinstance(part, dict)
    )
