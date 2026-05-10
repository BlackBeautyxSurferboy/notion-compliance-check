# Setting up the Notion Button → Webhook flow

This guide walks through wiring a Notion Button to your running NCC webhook so that one click in Notion triggers a full audit and posts the report back into the workspace.

> **Plan requirement.** Notion's `Send webhook` action is currently available on paid plans only. On the free plan, use `ncc audit --post` from the CLI — same outcome, no Button.

## Step 0 — Prerequisites

- NCC running locally (`ncc-webhook`) or hosted somewhere reachable from Notion.
- Notion integration installed in the workspace and connected to (a) the page you want audited and (b) the page you want reports nested under.
- `.env` has `NOTION_TOKEN`, `NCC_REPORT_PARENT_PAGE_ID`, and a strong `NCC_WEBHOOK_SECRET` set.

## Step 1 — Expose the webhook publicly

For local testing, ngrok is the path of least resistance:

```bash
ncc-webhook                      # in one terminal
ngrok http 8000                  # in another
```

Copy the `https://<random>.ngrok-free.app` URL ngrok prints. That is your public webhook host.

Production deploy: any host that runs FastAPI works (Render, Fly.io, Railway, your own VPS). The endpoint to expose is `POST /webhook/run-audit`.

## Step 2 — Add the Button block in Notion

1. In any Notion page, type `/button` and pick **Button**.
2. Label it **🔍 Run Compliance Audit**.
3. Click **+ Add action** → **Send webhook**.
4. **URL**: `https://<your-public-host>/webhook/run-audit`
5. **JSON body**:

   ```json
   {
     "secret": "<the value of NCC_WEBHOOK_SECRET in your .env>"
   }
   ```

   Optionally include a custom `parent_page_id` to override the env default:

   ```json
   {
     "secret": "…",
     "parent_page_id": "1f2…32-char-hex…cd"
   }
   ```

6. Save the action and the Button.

## Step 3 — Click it

You should see:
- `ncc-webhook` log a `POST /webhook/run-audit` returning 202.
- Within ~5–30 s (depending on workspace size), a new sub-page appears under your `NCC_REPORT_PARENT_PAGE_ID` parent, titled `Compliance Audit — YYYY-MM-DD (NN/100)`.

If the report does not appear:
- Check the webhook server logs for stack traces.
- Verify the integration is connected to the parent page (open the page → `…` → `Connections`).
- Verify the `secret` in the Button JSON matches `NCC_WEBHOOK_SECRET` exactly.

## Why a shared secret in the JSON body?

Notion's `Send webhook` action does not support custom request headers and does not sign the request. The next-best authentication primitive is a shared secret in the body, validated with `hmac.compare_digest` to avoid timing attacks. Once Notion ships signed webhooks, swap this for proper signature verification — see the roadmap in the README.
