"""Local CLI for running an audit against your Notion workspace.

Usage:
    ncc audit                    # run all checks, print findings to terminal
    ncc audit --post             # plus create a report page in Notion
    ncc audit --json             # output the full result as JSON
    ncc check pii_exposure       # run a single check

    ncc demo-setup               # populate workspace with demo content
    ncc demo-teardown            # archive every [NCC Demo] artifact

    ncc dashboard-setup          # create dashboard page + history DB
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
from ncc.dashboard import (
    setup_dashboard,
    write_audit_to_history,
)
from ncc.demo import setup_demo_workspace, teardown_demo_workspace
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


def _require_token() -> str | None:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        console.print("[red]NOTION_TOKEN is not set. Copy .env.example to .env first.[/]")
        return None
    return token


def _require_parent() -> str | None:
    parent = os.environ.get("NCC_REPORT_PARENT_PAGE_ID")
    if not parent:
        console.print(
            "[red]NCC_REPORT_PARENT_PAGE_ID is not set. "
            "Pick a Notion page, copy its 32-char ID from the URL, and add it to .env.[/]"
        )
        return None
    return parent


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
    else:
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


# ---------------------------------------------------------------------------
# audit / check
# ---------------------------------------------------------------------------


async def _audit(args: argparse.Namespace) -> int:
    token = _require_token()
    if not token:
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

        report_url: str | None = None
        if args.post:
            parent = _require_parent()
            if not parent:
                return 2
            with console.status("[cyan]Posting report to Notion..."):
                page = await write_report(client, parent_page_id=parent, result=result)
            report_url = page.get("url", "")
            console.print(f"[green]Report posted:[/] {report_url or page['id']}")

            history_db = os.environ.get("NCC_HISTORY_DB_ID")
            if history_db:
                with console.status("[cyan]Writing row to history DB..."):
                    await write_audit_to_history(
                        client,
                        history_db_id=history_db,
                        result=result,
                        report_page_url=report_url,
                    )
                console.print("[green]History row added.[/]")

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        _print_result(result)
    return 0


# ---------------------------------------------------------------------------
# demo-setup / demo-teardown
# ---------------------------------------------------------------------------


async def _demo_setup(_: argparse.Namespace) -> int:
    token = _require_token()
    if not token:
        return 2
    parent = _require_parent()
    if not parent:
        return 2

    async with NotionClient(token) as client:
        with console.status("[cyan]Creating demo workspace..."):
            artifacts = await setup_demo_workspace(client, parent_page_id=parent)

    console.print("[green]Demo workspace created.[/]\n")
    console.print(f"  📄 Sandbox-Page:    {artifacts.sandbox_page_url}")
    console.print(f"  📄 Q3-Public-Page:  {artifacts.public_page_url}")
    console.print(f"  📋 Risk-Database:   {artifacts.risk_db_url}\n")
    console.print(Panel.fit(
        "Manueller Schritt fürs CRITICAL-Trigger:\n\n"
        "Öffne die Q3-Page → Teilen → 'Im Web veröffentlichen' aktivieren.\n"
        "Die Notion-API darf das nicht automatisch tun.\n\n"
        "Aufräumen: ncc demo-teardown",
        title="Almost done",
    ))
    return 0


async def _demo_teardown(_: argparse.Namespace) -> int:
    token = _require_token()
    if not token:
        return 2

    async with NotionClient(token) as client:
        with console.status("[cyan]Archiving demo artifacts..."):
            n = await teardown_demo_workspace(client)
    console.print(f"[green]Archived {n} demo artifact(s).[/] (recoverable via Notion trash for 30 days)")
    return 0


# ---------------------------------------------------------------------------
# dashboard-setup
# ---------------------------------------------------------------------------


async def _dashboard_setup(_: argparse.Namespace) -> int:
    token = _require_token()
    if not token:
        return 2
    parent = _require_parent()
    if not parent:
        return 2

    async with NotionClient(token) as client:
        with console.status("[cyan]Creating dashboard + history DB..."):
            artifacts = await setup_dashboard(client, parent_page_id=parent)

    console.print("[green]Dashboard created.[/]\n")
    console.print(f"  🛡 Dashboard:    {artifacts.dashboard_page_url}")
    console.print(f"  📈 History-DB:   {artifacts.history_db_url}\n")
    console.print(Panel.fit(
        f"Add this line to your .env to enable history tracking:\n\n"
        f"NCC_HISTORY_DB_ID={artifacts.history_db_id}\n\n"
        "From the next 'ncc audit --post' onwards, every run adds a row "
        "with Score, Severity counts, and a link to its report page.",
        title="One more step",
    ))
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ncc",
        description="Notion Compliance Check — audit a Notion workspace for compliance risks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # audit
    audit_p = sub.add_parser("audit", help="Run all checks and print findings")
    audit_p.add_argument("--post", action="store_true", help="Also post the report into Notion")
    audit_p.add_argument("--json", action="store_true", help="Output JSON instead of a table")
    audit_p.set_defaults(check=None, _async=_audit)

    # check <id>
    check_p = sub.add_parser("check", help="Run a single check by id")
    check_p.add_argument("check", choices=list(_CHECK_BY_ID))
    check_p.add_argument("--post", action="store_true")
    check_p.add_argument("--json", action="store_true")
    check_p.set_defaults(_async=_audit)

    # demo-setup / demo-teardown
    setup_p = sub.add_parser(
        "demo-setup",
        help="Create demo content (sandbox page, sensitive-title page, risk DB)",
    )
    setup_p.set_defaults(_async=_demo_setup)

    teardown_p = sub.add_parser(
        "demo-teardown",
        help="Archive every demo artifact (titles starting with [NCC Demo])",
    )
    teardown_p.set_defaults(_async=_demo_teardown)

    # dashboard-setup
    dash_p = sub.add_parser(
        "dashboard-setup",
        help="Create the compliance dashboard page + history database",
    )
    dash_p.set_defaults(_async=_dashboard_setup)

    args = parser.parse_args(argv)
    return asyncio.run(args._async(args))


if __name__ == "__main__":
    sys.exit(main())
