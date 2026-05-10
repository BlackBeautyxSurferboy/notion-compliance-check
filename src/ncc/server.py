"""MCP server exposing Notion Compliance Check as tools and resources.

Run with one of:
    ncc-mcp                            # stdio transport (default — for local Claude Desktop / Code)
    NCC_TRANSPORT=http ncc-mcp         # streamable-http for hosted deployments
    NCC_TRANSPORT=sse ncc-mcp          # legacy SSE transport

Tools:
    run_audit                — runs every check, returns score + findings JSON.
    run_audit_and_post       — runs every check and posts the report into Notion.
    check_public_access      — single-check variant.
    check_orphaned_pages     — single-check variant.
    check_stale_data         — single-check variant.
    check_pii_exposure       — single-check variant.

Resources:
    ncc://about              — short capability summary suitable for an LLM system prompt.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from ncc.audit import run_audit
from ncc.checks import (
    Check,
    OrphanedPagesCheck,
    PIIExposureCheck,
    PublicAccessCheck,
    StaleDataCheck,
)
from ncc.notion_client import NotionClient
from ncc.report import write_report

load_dotenv()

mcp = FastMCP("Notion Compliance Check")


def _token() -> str:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError(
            "NOTION_TOKEN is not set. Create an internal integration at "
            "https://www.notion.so/my-integrations and export the secret."
        )
    return token


async def _run_single(check: Check) -> dict[str, Any]:
    async with NotionClient(_token()) as client:
        result = await run_audit(client, checks=[check])
    return result.to_dict()


@mcp.tool()
async def run_audit_full() -> dict[str, Any]:
    """Run every compliance check against the Notion workspace.

    Returns a JSON object with the compliance score (0–100), per-finding details,
    and any errors encountered. Does NOT write anything to Notion — read-only.
    """
    async with NotionClient(_token()) as client:
        result = await run_audit(client)
    return result.to_dict()


@mcp.tool()
async def run_audit_and_post(parent_page_id: str | None = None) -> dict[str, Any]:
    """Run every check and post the formatted report as a sub-page in Notion.

    Args:
        parent_page_id: Notion page ID to nest the report under. Defaults to
            NCC_REPORT_PARENT_PAGE_ID from env if omitted.

    Returns:
        { "score": int, "report_url": str, "report_page_id": str, "summary": str }
    """
    parent = parent_page_id or os.environ.get("NCC_REPORT_PARENT_PAGE_ID")
    if not parent:
        raise ValueError(
            "parent_page_id was not provided and NCC_REPORT_PARENT_PAGE_ID is not set."
        )

    async with NotionClient(_token()) as client:
        result = await run_audit(client)
        page = await write_report(client, parent_page_id=parent, result=result)

    return {
        "score": result.score,
        "summary": result.summary_line(),
        "report_page_id": page["id"],
        "report_url": page.get("url", ""),
    }


@mcp.tool()
async def check_public_access() -> dict[str, Any]:
    """Detect pages exposed to the public web (DSGVO Art. 32, SOC 2 CC6.1)."""
    return await _run_single(PublicAccessCheck())


@mcp.tool()
async def check_orphaned_pages() -> dict[str, Any]:
    """Find database pages with no assigned owner (ISO 27001 A.5.2)."""
    return await _run_single(OrphanedPagesCheck())


@mcp.tool()
async def check_stale_data(threshold_days: int = 365) -> dict[str, Any]:
    """List pages not edited for `threshold_days` (DSGVO Art. 5(1)(d))."""
    return await _run_single(StaleDataCheck(threshold_days=threshold_days))


@mcp.tool()
async def check_pii_exposure() -> dict[str, Any]:
    """Scan page content for plaintext PII (credit cards, IBAN, tax IDs, secrets)."""
    return await _run_single(PIIExposureCheck())


@mcp.resource("ncc://about")
def about() -> str:
    return (
        "Notion Compliance Check (NCC) audits a Notion workspace for IT and company "
        "compliance risks. It runs four checks: public web exposure, orphaned pages "
        "(no owner), stale data (last edited beyond threshold), and plaintext PII "
        "(credit cards Luhn-validated, IBAN mod-97-validated, German tax IDs, US SSN, "
        "embedded passwords/API keys). Findings are mapped to DSGVO, ISO 27001, "
        "SOC 2 and PCI-DSS controls. Use the run_audit_full tool for read-only audits "
        "or run_audit_and_post to materialise the report as a Notion sub-page."
    )


def run() -> None:
    transport = os.environ.get("NCC_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    run()
