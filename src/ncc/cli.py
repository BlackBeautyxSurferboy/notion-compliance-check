"""Local CLI for running an audit against your Notion workspace.

Usage:
    ncc audit                    # run all checks, print report to terminal
    ncc audit --post             # run all checks AND create a report page in Notion
    ncc audit --json             # output the full result as JSON (for scripting)
    ncc check pii_exposure       # run a single check
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ncc.audit import AuditResult, run_audit
from ncc.checks import (
    ALL_CHECKS,
    OrphanedPagesCheck,
    PIIExposureCheck,
    PublicAccessCheck,
    Severity,
    StaleDataCheck,
)
from ncc.notion_client import NotionClient
from ncc.report import write_report

load_dotenv(override=True)
console = Console()

_SEVERITY_COLOR = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "white",
}

_CHECK_BY_ID = {
    "public_access": PublicAccessCheck,
    "orphaned_pages": OrphanedPagesCheck,
    "stale_data": StaleDataCheck,
    "pii_exposure": PIIExposureCheck,
}


def _print_result(result: AuditResult) -> None:
    score = result.score
    if score is None:
        score_style, score_text = "bold red", "N/A"
    elif score >= 90:
        score_style, score_text = "bold green", f"{score}/100"
    elif score >= 70:
        score_style, score_text = "bold yellow", f"{score}/100"
    else:
        score_style, score_text = "bold red", f"{score}/100"
    console.print(Panel.fit(
        f"[{score_style}]{score_text}[/] — {result.summary_line()}",
        title="Notion Compliance Check",
    ))

    if not result.findings:
        console.print("[green]No findings — workspace looks clean.[/]")
        return

    table = Table(show_lines=False, header_style="bold cyan")
    table.add_column("Severity", width=10)
    table.add_column("Check", width=18)
    table.add_column("Title", overflow="fold")
    table.add_column("Refs", overflow="fold")

    for f in result.findings:
        style = _SEVERITY_COLOR[f.severity]
        table.add_row(
            f"[{style}]{f.severity.emoji} {f.severity.value}[/]",
            f.check_id,
            f.title,
            ", ".join(f.framework_refs),
        )
    console.print(table)

    if result.errors:
        console.print("[red]Errors:[/]")
        for cid, msg in result.errors.items():
            console.print(f"  [red]{cid}[/]: {msg}")


async def _audit(args: argparse.Namespace) -> int:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        console.print("[red]NOTION_TOKEN is not set. Copy .env.example to .env first.[/]")
        return 2

    if args.check:
        check_cls = _CHECK_BY_ID.get(args.check)
        if not check_cls:
            console.print(f"[red]Unknown check '{args.check}'. Available: {list(_CHECK_BY_ID)}[/]")
            return 2
        checks = [check_cls()]
    else:
        checks = [c() for c in ALL_CHECKS]

    async with NotionClient(token) as client:
        with console.status("[cyan]Running compliance audit..."):
            result = await run_audit(client, checks=checks)

        if args.post:
            parent = os.environ.get("NCC_REPORT_PARENT_PAGE_ID")
            if not parent:
                console.print("[red]--post requires NCC_REPORT_PARENT_PAGE_ID in your .env[/]")
                return 2
            with console.status("[cyan]Posting report to Notion..."):
                page = await write_report(client, parent_page_id=parent, result=result)
            console.print(f"[green]Report posted:[/] {page.get('url', page['id'])}")

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        _print_result(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ncc",
        description="Notion Compliance Check — audit a Notion workspace for compliance risks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit_p = sub.add_parser("audit", help="Run all checks and print findings")
    audit_p.add_argument("--post", action="store_true", help="Also post the report into Notion")
    audit_p.add_argument("--json", action="store_true", help="Output JSON instead of a table")
    audit_p.set_defaults(check=None)

    check_p = sub.add_parser("check", help="Run a single check by id")
    check_p.add_argument("check", choices=list(_CHECK_BY_ID))
    check_p.add_argument("--post", action="store_true")
    check_p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    return asyncio.run(_audit(args))


if __name__ == "__main__":
    sys.exit(main())
