"""FastAPI webhook endpoint triggered by a Notion Button.

Notion's native webhook action sends an unauthenticated POST. We protect it with
a shared secret in the JSON body — the Button is configured to send
    { "secret": "<NCC_WEBHOOK_SECRET>" }
and we reject anything else with a 401.
"""

from __future__ import annotations

import asyncio
import hmac
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from ncc.audit import run_audit
from ncc.notion_client import NotionClient
from ncc.report import write_report

load_dotenv(override=True)

app = FastAPI(
    title="Notion Compliance Check Webhook",
    description="Triggered by a Notion Button to run a compliance audit.",
    version="0.1.0",
)


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise HTTPException(
            status_code=500, detail=f"Server misconfigured: {key} is not set."
        )
    return value


def _check_secret(body: dict[str, Any]) -> None:
    expected = os.environ.get("NCC_WEBHOOK_SECRET")
    if not expected:
        return  # no secret configured = open endpoint (dev only)
    provided = str(body.get("secret", ""))
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing secret.")


async def _run_and_post(parent_page_id: str) -> None:
    token = _require_env("NOTION_TOKEN")
    async with NotionClient(token) as client:
        result = await run_audit(client)
        await write_report(client, parent_page_id=parent_page_id, result=result)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/run-audit")
async def trigger_audit(request: Request, background: BackgroundTasks) -> dict[str, str]:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    _check_secret(body)

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

    # Notion's webhook caller times out fast, so run the audit in the background.
    background.add_task(asyncio.create_task, _run_and_post(parent_page_id))
    return {"status": "accepted", "message": "Audit started; report will be posted to Notion."}


def run() -> None:
    import uvicorn

    # Hosting platforms (Render, Fly, Heroku, Cloud Run, …) inject PORT.
    # Fall back to NCC_WEBHOOK_PORT for local development, then 8000.
    port = int(
        os.environ.get("PORT")
        or os.environ.get("NCC_WEBHOOK_PORT")
        or "8000"
    )
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
