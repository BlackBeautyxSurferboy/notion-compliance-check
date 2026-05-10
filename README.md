# Notion Compliance Check (NCC)

> An MCP server that audits a Notion workspace for IT and company compliance risks — DSGVO, ISO 27001, SOC 2, PCI-DSS — and writes the report straight back into Notion as a formatted page.

NCC is not a SaaS layer on top of Notion. It is built on the same primitives Notion's own platform team is investing in: **MCP (Model Context Protocol)** and the **public Notion API with native webhook actions**. That choice is deliberate — see [Architecture](#architecture) below, or read [docs/build-process.md](docs/build-process.md) for the full decision journey.

---

## What it checks

| ID | Check | Severity range | Frameworks |
|---|---|---|---|
| `public_access` | Pages exposed to the public web, with sensitive-keyword title scan | HIGH–CRITICAL | DSGVO Art. 32, SOC 2 CC6.1, ISO 27001 A.5.10 |
| `orphaned_pages` | Database pages with an empty Owner / Verantwortlich property | MEDIUM | ISO 27001 A.5.2, SOC 2 CC1.3 |
| `stale_data` | Pages not edited beyond a configurable threshold (default 365 d) | LOW–MEDIUM | DSGVO Art. 5(1)(d), ISO 27001 A.5.34 |
| `pii_exposure` | Plaintext credit cards (Luhn-validated), IBANs (mod-97-validated), German tax IDs, US SSN, embedded passwords / API keys | HIGH–CRITICAL | DSGVO Art. 9, Art. 32, PCI-DSS Req 3.4 |

Each finding ships with a severity, a human-readable explanation, a deep link back to the offending Notion page, and the relevant control references — so the output is ready to paste into a SOC 2 or DSGVO evidence binder.

A simple weighted score (0–100) summarises the overall posture: 25 points off per critical finding, 10 per high, 4 per medium, 1 per low, floored at 0.

---

## Architecture

```
┌────────────────────────────┐         ┌────────────────────────────┐
│  Notion workspace          │         │  Notion AI / Claude / any  │
│  ┌──────────────────────┐  │         │  MCP-aware client          │
│  │ "Run Compliance      │  │         └─────────────┬──────────────┘
│  │  Audit" Button       │──┼── HTTPS POST          │ MCP (stdio /
│  │  (Send webhook       │  │  + shared secret      │  streamable-http)
│  │   action)            │  │                       │
│  └──────────────────────┘  │                       │
└────────────────────────────┘                       │
              │                                      │
              ▼                                      ▼
   ┌──────────────────────┐              ┌──────────────────────┐
   │  FastAPI webhook     │              │  FastMCP server      │
   │  /webhook/run-audit  │              │  src/ncc/server.py   │
   │  src/ncc/webhook.py  │              │                      │
   └──────────┬───────────┘              └──────────┬───────────┘
              │                                     │
              └────────────────┬────────────────────┘
                               ▼
                  ┌────────────────────────┐
                  │  Audit orchestrator    │
                  │  src/ncc/audit.py      │
                  └────────────┬───────────┘
                               │ asyncio.gather
       ┌───────────────┬───────┴───────┬─────────────────┐
       ▼               ▼               ▼                 ▼
  public_access  orphaned_pages  stale_data        pii_exposure
       │               │               │                 │
       └───────────────┴───────┬───────┴─────────────────┘
                               ▼
                  ┌────────────────────────┐
                  │  Notion API (async)    │
                  │  src/ncc/notion_client │
                  └────────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │  Report builder        │
                  │  src/ncc/report.py     │
                  │  (callouts, toggles,   │
                  │   severity colors)     │
                  └────────────┬───────────┘
                               ▼
                       new sub-page in Notion
```

Two surfaces, one core. The MCP server lets Notion AI or Claude trigger an audit conversationally. The webhook lets a Notion Button trigger the same audit with one click. Both call the same `audit.py` orchestrator, the same checks, and produce the same Notion-native report.

---

## Why MCP, not a Notion "slash command"

The first idea I had was a `/ncc` slash command in Notion. After reading the API docs, three things became clear:

1. **Notion does not currently expose `/`-menu extension points to third parties.** That door is closed today.
2. **Notion has gone all-in on MCP.** First-party MCP server, deep tooling investment, AI Connectors. Building on MCP is building on where the platform is going, not where it was.
3. **The closest user-experience match — "click a button, get a result back in your workspace" — is achievable today** via Notion's native `Send webhook` button action.

So: MCP server for the *agent-driven* path, FastAPI webhook for the *button-click* path. No Zapier, no Make, no middleware.

---

## Quick start

### 1. Notion setup

1. Create an internal integration at <https://www.notion.so/my-integrations>. Copy the secret token.
2. In the workspace you want to audit, open each top-level page → `...` → `Connections` → connect your integration.
3. Pick (or create) a page where reports should land. Copy its 32-char ID from the URL.

### 2. Local install

```bash
git clone https://github.com/BlackBeautyxSurferboy/notion-compliance-check.git
cd notion-compliance-check
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env: NOTION_TOKEN, NCC_REPORT_PARENT_PAGE_ID, NCC_WEBHOOK_SECRET
```

### 3. Run an audit (CLI)

```bash
ncc audit                  # pretty-printed table in your terminal
ncc audit --json           # JSON output, for piping into anything
ncc audit --post           # also write the report into Notion
ncc check pii_exposure     # run a single check
```

### 4. Run as MCP server

```bash
ncc-mcp                              # stdio transport (Claude Desktop, Claude Code)
NCC_TRANSPORT=streamable-http ncc-mcp  # HTTP transport (hosted)
```

For Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "notion-compliance-check": {
      "command": "/path/to/.venv/bin/ncc-mcp",
      "env": {
        "NOTION_TOKEN": "secret_…",
        "NCC_REPORT_PARENT_PAGE_ID": "…"
      }
    }
  }
}
```

### 5. Run as webhook (for the Notion Button demo)

```bash
ncc-webhook                  # listens on :8000
# expose with ngrok / cloudflared for the Notion Button to reach it:
ngrok http 8000
```

In Notion: add a Button block → action `Send webhook` → URL = your public webhook URL → JSON body:

```json
{ "secret": "<NCC_WEBHOOK_SECRET from your .env>" }
```

Click the button → the audit runs in the background → a new report page appears under your configured parent page within ~10 seconds.

> ⚠ **Notion's native webhook action requires a paid Notion plan** at the time of writing. On the free plan, use `ncc audit --post` from the CLI instead — same output.

See [docs/notion-button-setup.md](docs/notion-button-setup.md) for screenshots and a step-by-step.

---

## MCP tools exposed

| Tool | Purpose |
|---|---|
| `run_audit_full` | Read-only: returns score + findings JSON. |
| `run_audit_and_post` | Runs the full audit and writes the report into Notion. |
| `check_public_access` | Single-check variant (read-only). |
| `check_orphaned_pages` | Single-check variant. |
| `check_stale_data` | Single-check variant; takes a `threshold_days` arg. |
| `check_pii_exposure` | Single-check variant. |

Resource: `ncc://about` — short capability summary, useful as system-prompt context.

---

## Tests

```bash
pytest -q
```

The PII validators are covered with both positive cases (real Visa/Mastercard/IBAN test numbers) and negative cases (random digit strings) — Luhn and mod-97 must accept the former and reject the latter, which is the difference between a useful compliance scan and noise.

---

## Roadmap

If this were going to production, the next things on the list would be:
- **External-guest audit** — flag pages shared with guests outside the org's primary domain.
- **Sharing-graph diff** — compare today's permission graph against last week's, alert on widening exposure.
- **Custom check DSL** — let compliance officers write rules in YAML rather than Python.
- **Evidence export** — package findings into the auditor-friendly format (CSV per control + linked-evidence ZIP).
- **Webhook signature verification** — once Notion adds signed webhooks, drop the shared-secret-in-body hack.

---

## License

MIT — see [LICENSE](LICENSE).
