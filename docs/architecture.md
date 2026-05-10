# Architecture

## Module layout

```
src/ncc/
├── __init__.py
├── __main__.py            # `python -m ncc audit` entry point
├── notion_client.py       # async httpx wrapper around the Notion REST API
├── audit.py               # orchestrator — runs checks in parallel, aggregates findings, scores
├── report.py              # turns an AuditResult into Notion blocks + creates the report page
├── server.py              # FastMCP server (stdio / streamable-http)
├── webhook.py             # FastAPI webhook endpoint for the Notion Button trigger
├── cli.py                 # rich-formatted CLI — `ncc audit`, `ncc check <id>`
└── checks/
    ├── __init__.py        # exposes ALL_CHECKS
    ├── base.py            # Severity, Finding, Check ABC
    ├── public_access.py   # web-exposed pages + sensitive-keyword title scan
    ├── orphaned_pages.py  # database pages without an Owner
    ├── stale_data.py      # pages older than threshold
    └── pii.py             # plaintext PII scan (Luhn + mod-97 validators)
```

## Data flow

1. **Trigger** — either an MCP client invokes `run_audit_full` / `run_audit_and_post`, the Notion Button posts to `/webhook/run-audit`, or the user runs `ncc audit --post`.
2. **Audit orchestrator (`audit.run_audit`)** — instantiates every registered `Check` and runs them concurrently with `asyncio.gather(..., return_exceptions=True)`. Failures in one check never abort the audit.
3. **Each check** — pages through the Notion API using cursor-based pagination, produces `Finding` objects with severity, control references, and a deep link.
4. **Aggregation** — findings are sorted by severity, scored (25/10/4/1 weighted, floored at 0), and packaged into an `AuditResult`.
5. **Report generation (`report.build_report_blocks`)** — `AuditResult` becomes Notion block JSON: callout for the score, severity breakdown, per-check toggles. Notion's 100-children-per-request cap is respected.
6. **Persistence** — when the caller asks for it, the orchestrator creates a sub-page under the configured parent and appends report blocks in 100-block chunks.

## Concurrency model

- The `audit.py` orchestrator parallelises **across checks**.
- Inside `pii.py`, scanning per-page is parallelised with a `Semaphore(5)` so we don't fan-out hundreds of `retrieve_block_children` calls simultaneously.
- The Notion client retries 429 responses up to 3 times with the `Retry-After` header value.

## Security boundaries

- **Webhook authentication**: shared secret in the JSON body, compared with `hmac.compare_digest`. Notion's webhook action does not sign requests, so this is the next-best primitive.
- **Token storage**: integration token is read from `NOTION_TOKEN` env var. Never logged; never written to disk.
- **Read-only by default**: the `run_audit_full`, single-check tools, and CLI without `--post` never call any write endpoint. Writes happen only through `run_audit_and_post`, the CLI `--post` flag, or the webhook (which is the explicit "create report" path).

## What's intentionally not here

- A persistent storage layer for historical audits. Reports live in Notion — that is the storage layer.
- Authentication on the MCP server. Stdio transport is local-only by definition; for `streamable-http`, deploy behind whatever auth proxy fits the host (the FastMCP `auth` parameter is the seam for that).
- Configuration via Notion DB. Could be added; for v0.1 the env-var approach keeps the surface small.
