# Sample Audit Report (rendered as Markdown)

> What an NCC report looks like in your Notion workspace, simplified to Markdown for the README. Real reports use Notion callouts, toggles, and severity-coded background colors.

---

📊 **Score 64/100 — 1 critical, 3 high, 4 medium, 12 low (took 4.7s)**

Generated at 2026-05-10T10:14:32+00:00 by Notion Compliance Check (NCC).

---

## Severity breakdown

- 🔴 **CRITICAL**: 1 finding(s)
- 🟠 **HIGH**: 3 finding(s)
- 🟡 **MEDIUM**: 4 finding(s)
- 🔵 **LOW**: 12 finding(s)

---

## Findings by check

### ▾ public_access — 2 finding(s)

🔴 **Public page: Q3 2026 Financials — confidential**
*[open in Notion ↗](https://www.notion.so/example/q3-financials)*

Page is publicly accessible AND its title contains the sensitive keyword 'financ'. Anyone with the link can read it.

Framework: DSGVO Art. 32 · DSGVO Art. 5(1)(f) · SOC 2 CC6.1 · ISO 27001 A.5.10

---

🟠 **Public page: Engineering all-hands notes**
*[open in Notion ↗](https://www.notion.so/example/eng-all-hands)*

Page is publicly accessible. Even if the title looks harmless, review its content and confirm the public exposure is intentional.

Framework: DSGVO Art. 32 · SOC 2 CC6.1

---

### ▾ pii_exposure — 2 finding(s)

🟠 **PII (iban): Customer onboarding template**
*[open in Notion ↗](https://www.notion.so/example/onboarding)*

Found 3 match(es) of pattern 'iban' in page content. Redacted preview: DE89****************, GB82****************, FR14**********************

Framework: DSGVO Art. 32

---

🟠 **PII (email_with_password_context): Deploy runbook**
*[open in Notion ↗](https://www.notion.so/example/deploy)*

Found 1 match(es) of pattern 'email_with_password_context' in page content. Redacted preview: API_K***************************

Framework: DSGVO Art. 32 · ISO 27001 A.5.17

---

### ▾ orphaned_pages — 4 finding(s)

🟡 **No owner: Vendor risk assessment — Acme Corp**
*[open in Notion ↗](https://www.notion.so/example/acme-risk)*

Page in database 'Vendor Risk Register' has an empty 'Owner' property. Assign someone responsible.

Framework: ISO 27001 A.5.2 · SOC 2 CC1.3

*(3 more orphaned pages omitted in this preview)*

---

### ▾ stale_data — 12 finding(s)

🔵 **Stale (412d): Onboarding checklist v2**
*[open in Notion ↗](https://www.notion.so/example/onboarding-v2)*

Page last edited 412 days ago (2025-03-25). Threshold is 365 days. Review, update, or archive.

Framework: DSGVO Art. 5(1)(d) · ISO 27001 A.5.34

*(11 more stale pages omitted in this preview)*

---

In Notion, each toggle is collapsible, callout severities are colour-coded (red / orange / yellow / blue background), and every page reference is a clickable deep link.
