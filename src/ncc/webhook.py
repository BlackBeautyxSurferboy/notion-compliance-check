"""FastAPI app: Notion-button webhook endpoint + REST API for the embed widget.

The single FastAPI app exposes:

- POST /webhook/run-audit       — Notion Button → triggers audit (header-auth)
- GET  /widget?key=...          — Embeddable HTML widget for /embed in Notion
- POST /api/audit/trigger?key=  — Start an audit, returns job_id (widget uses this)
- GET  /api/audit/status/{id}   — Poll job state (running / done / error)
- GET  /api/audit/latest        — Latest row from the history DB (read-only)
- GET  /api/audit/history?limit=N — Recent rows from the history DB (read-only)
- GET  /health                  — Render health check

Read-only API endpoints are intentionally unauthenticated — they only expose
already-aggregated counts (score, severity totals, dates), no findings or
page content. Writes (trigger) require the shared secret as ?key= query.
"""

from __future__ import annotations

import hmac
import os
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from ncc.audit import run_audit
from ncc.checks import Severity
from ncc.dashboard import write_audit_to_history
from ncc.notion_client import NotionClient
from ncc.report import write_report

load_dotenv(override=True)

app = FastAPI(
    title="Notion Compliance Check",
    description="Webhook + REST API + embeddable widget for NCC audits.",
    version="0.2.0",
)

_STATIC_DIR = Path(__file__).parent / "static"

# In-memory job tracking. State is lost on restart — fine for a demo widget;
# a production deployment would use Redis or a small DB.
_jobs: dict[str, dict[str, Any]] = {}


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise HTTPException(
            status_code=500, detail=f"Server misconfigured: {key} is not set."
        )
    return value


def _check_key(provided: str) -> None:
    """Validate a key passed via ?key=… query parameter."""
    expected = os.environ.get("NCC_WEBHOOK_SECRET")
    if not expected:
        return
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing key.")


def _check_secret(request: Request, body: dict[str, Any]) -> None:
    """For the legacy /webhook/run-audit Notion-Button endpoint.

    Accepts the shared secret via three channels, in this order:
        1. X-NCC-Secret header  (Notion Button friendly)
        2. Authorization: Bearer <secret>  (curl / generic webhooks)
        3. secret field in JSON body  (legacy / CLI tests)
    """
    expected = os.environ.get("NCC_WEBHOOK_SECRET")
    if not expected:
        return

    candidates: list[str] = []
    header = request.headers.get("x-ncc-secret")
    if header:
        candidates.append(header)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        candidates.append(auth[7:].strip())
    body_secret = body.get("secret")
    if body_secret:
        candidates.append(str(body_secret))

    for candidate in candidates:
        if hmac.compare_digest(candidate, expected):
            return

    raise HTTPException(status_code=401, detail="Invalid or missing secret.")


# ---------------------------------------------------------------------------
# Core audit runner (shared between webhook and widget API)
# ---------------------------------------------------------------------------


async def _run_and_post(parent_page_id: str, job_id: str | None = None) -> None:
    """Run a full audit, write the report page, append history row.

    When job_id is given, updates the in-memory _jobs entry so the widget can
    poll status. Errors are captured into the job entry rather than re-raised
    so a single failing run doesn't kill the FastAPI worker.
    """
    if job_id:
        _jobs[job_id]["status"] = "running"

    try:
        token = _require_env("NOTION_TOKEN")
        async with NotionClient(token) as client:
            result = await run_audit(client)
            page = await write_report(client, parent_page_id=parent_page_id, result=result)
            history_db = os.environ.get("NCC_HISTORY_DB_ID")
            if history_db:
                await write_audit_to_history(
                    client,
                    history_db_id=history_db,
                    result=result,
                    report_page_url=page.get("url"),
                )

        if job_id:
            _jobs[job_id].update({
                "status": "done",
                "finished_at": time.time(),
                "score": result.score,
                "summary": result.summary_line(),
                "report_url": page.get("url"),
                "counts": {sev.value: len(result.by_severity[sev]) for sev in Severity},
            })
    except Exception as exc:
        if job_id:
            _jobs[job_id].update({
                "status": "error",
                "finished_at": time.time(),
                "error": f"{type(exc).__name__}: {exc}",
            })
        else:
            raise


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Notion history-DB row into a widget-friendly JSON shape."""
    props = row.get("properties", {})

    def _read(key: str, type_: str) -> Any:
        prop = props.get(key, {})
        if type_ == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
        if type_ == "number":
            return prop.get("number")
        if type_ == "date":
            d = prop.get("date") or {}
            return d.get("start")
        if type_ == "select":
            s = prop.get("select") or {}
            return s.get("name") if s else None
        if type_ == "url":
            return prop.get("url")
        return None

    return {
        "id": row.get("id"),
        "run": _read("Run", "title"),
        "date": _read("Datum", "date"),
        "score": _read("Score", "number"),
        "status": _read("Status", "select"),
        "critical": _read("Critical", "number") or 0,
        "high": _read("High", "number") or 0,
        "medium": _read("Medium", "number") or 0,
        "low": _read("Low", "number") or 0,
        "duration": _read("Dauer (s)", "number"),
        "report_url": _read("Report-Page", "url"),
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Legacy Notion-Button webhook
# ---------------------------------------------------------------------------


@app.post("/webhook/run-audit")
async def trigger_audit(request: Request, background: BackgroundTasks) -> dict[str, str]:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    _check_secret(request, body)

    parent_page_id = (
        body.get("parent_page_id")
        or os.environ.get("NCC_REPORT_PARENT_PAGE_ID")
    )
    if not parent_page_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "parent_page_id missing in request body and "
                "NCC_REPORT_PARENT_PAGE_ID env var is not set."
            ),
        )

    background.add_task(_run_and_post, parent_page_id)
    return {"status": "accepted", "message": "Audit started; report will be posted to Notion."}


# ---------------------------------------------------------------------------
# Widget REST API
# ---------------------------------------------------------------------------


@app.post("/api/audit/trigger")
async def api_trigger(request: Request, background: BackgroundTasks) -> dict[str, str]:
    """Start an audit. Returns a job_id; client polls /api/audit/status/{id}."""
    _check_key(request.query_params.get("key", ""))

    parent_page_id = os.environ.get("NCC_REPORT_PARENT_PAGE_ID")
    if not parent_page_id:
        raise HTTPException(500, "Server missing NCC_REPORT_PARENT_PAGE_ID.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "started_at": time.time(),
    }
    background.add_task(_run_and_post, parent_page_id, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/audit/status/{job_id}")
async def api_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job_id.")
    return {"job_id": job_id, **job}


@app.get("/api/audit/latest")
async def api_latest() -> dict[str, Any]:
    db_id = os.environ.get("NCC_HISTORY_DB_ID")
    if not db_id:
        return {"available": False, "reason": "NCC_HISTORY_DB_ID not configured."}
    token = _require_env("NOTION_TOKEN")
    try:
        async with NotionClient(token) as client:
            rows = await client.query_database_recent(db_id, limit=1)
    except Exception as exc:
        # Most common cause: history DB lost its integration connection.
        # Don't bring the widget down — show "no data" and let user reconnect.
        return {"available": False, "reason": f"DB unreachable: {type(exc).__name__}"}
    if not rows:
        return {"available": False, "reason": "No audits yet."}
    return {"available": True, "row": _serialize_row(rows[0])}


@app.get("/api/audit/history")
async def api_history(limit: int = 5) -> dict[str, Any]:
    db_id = os.environ.get("NCC_HISTORY_DB_ID")
    if not db_id:
        return {"rows": [], "reason": "NCC_HISTORY_DB_ID not configured."}
    token = _require_env("NOTION_TOKEN")
    try:
        async with NotionClient(token) as client:
            rows = await client.query_database_recent(db_id, limit=limit)
    except Exception as exc:
        return {"rows": [], "reason": f"DB unreachable: {type(exc).__name__}"}
    return {"rows": [_serialize_row(r) for r in rows]}


# ---------------------------------------------------------------------------
# Widget HTML (Notion-embeddable)
# ---------------------------------------------------------------------------


@app.get("/widget", response_class=HTMLResponse)
async def widget(request: Request) -> str:
    """Render the embeddable widget. ?key=... is required to enable the Run button.

    Without a valid key, the widget renders read-only (shows latest score +
    history but cannot trigger new audits). This lets you share the page URL
    without leaking the trigger capability.
    """
    key = request.query_params.get("key", "")
    expected = os.environ.get("NCC_WEBHOOK_SECRET") or ""
    can_trigger = bool(expected) and hmac.compare_digest(key, expected)

    html_path = _STATIC_DIR / "widget.html"
    html = html_path.read_text(encoding="utf-8")
    return (
        html
        .replace("__AUTH_KEY__", key if can_trigger else "")
        .replace("__CAN_TRIGGER__", "true" if can_trigger else "false")
    )


def run() -> None:
    import uvicorn

    port = int(
        os.environ.get("PORT")
        or os.environ.get("NCC_WEBHOOK_PORT")
        or "8000"
    )
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
