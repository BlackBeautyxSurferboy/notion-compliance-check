# 🛡 Notion Compliance Check

Mein Notion-Workspace ist mit der Zeit zu einem zweiten Gehirn geworden. Notizen, Reisepläne, Pitches, Steuerunterlagen, Vertragsentwürfe, eine zu lange Liste an Logins. Irgendwann letzten Monat hab ich gemerkt: ich teile Pages, ohne mich daran zu erinnern, was ich geteilt hab. Ich hab Pages aus 2023, von denen ich nicht mehr weiß, ob sie noch stimmen. Ich hab definitiv mal eine IBAN da reingepastet.

Compliance-Tools dafür gibt's — alle für Enterprise, alle teuer, alle für Workspaces, in denen jemand Vollzeit Compliance Officer ist. Für mich, mit meinem privaten Workspace, gibt's nichts. Also hab ich's gebaut.

**NCC scannt einen Notion-Workspace auf vier konkrete Risiken** — öffentliche Pages mit sensiblen Inhalten, Pages ohne Owner, veraltete Daten, Plaintext-PII (Kreditkarten, IBANs, Passwörter, API-Keys). Jedes Finding ist mit einer konkreten Norm verknüpft (DSGVO Art. 32, ISO 27001 A.5.2, PCI-DSS Req 3.4, …). Output: ein formatierter Report direkt zurück in den Workspace, severity-codiert, mit Deeplinks zu den problematischen Pages.

> **Repo:** [github.com/BlackBeautyxSurferboy/notion-compliance-check](https://github.com/BlackBeautyxSurferboy/notion-compliance-check)
> **Demo (2:45):** _Loom-Link einfügen_

---

## Wie man's bedient

Zwei Wege, ein Kern.

**1. Klick.** Notion-Button in einer Page → Audit läuft → Report-Page erscheint im Workspace. Funktioniert über Notions native `Send webhook`-Action — kein Zapier, kein Make, kein Middleware-Geraffel.

**2. Konversationell.** NCC ist ein MCP-Server. Notion AI oder Claude können den Audit triggern, indem sie Tools wie `run_audit_and_post` oder `check_pii_exposure` aufrufen. Nutzt Notions strategische Plattform-Richtung — MCP statt klassische REST-Integration.

Beides ruft denselben Audit-Orchestrator auf, dieselben Checks, denselben Report-Builder.

---

## Architektur

```
┌────────────────────────────┐         ┌────────────────────────────┐
│  Notion-Workspace          │         │  Notion AI / Claude /      │
│  ┌──────────────────────┐  │         │  jeder MCP-aware Client    │
│  │ "Run Compliance      │  │         └─────────────┬──────────────┘
│  │  Audit" Button       │──┼── HTTPS POST          │ MCP (stdio /
│  │  (Send webhook)      │  │  + shared secret      │  streamable-http)
│  └──────────────────────┘  │                       │
└────────────────────────────┘                       │
              │                                      │
              ▼                                      ▼
   ┌──────────────────────┐              ┌──────────────────────┐
   │  FastAPI Webhook     │              │  FastMCP Server      │
   │  /webhook/run-audit  │              │  src/ncc/server.py   │
   └──────────┬───────────┘              └──────────┬───────────┘
              │                                     │
              └────────────────┬────────────────────┘
                               ▼
                  ┌────────────────────────┐
                  │  Audit-Orchestrator    │
                  │  (asyncio.gather)      │
                  └────────────┬───────────┘
                               │
       ┌───────────────┬───────┴───────┬─────────────────┐
       ▼               ▼               ▼                 ▼
  public_access  orphaned_pages  stale_data        pii_exposure
       │               │               │                 │
       └───────────────┴───────┬───────┴─────────────────┘
                               ▼
                  ┌────────────────────────┐
                  │  Notion REST API       │
                  │  (async, cursor-pag.)  │
                  └────────────┬───────────┘
                               ▼
                  ┌────────────────────────┐
                  │  Report-Builder        │
                  │  Callouts, Toggles,    │
                  │  severity-coded        │
                  └────────────┬───────────┘
                               ▼
                       neue Sub-Page in Notion
```

---

## Die vier Checks

| Check | Severity | Verankert in |
|---|---|---|
| **Public Web Exposure** — Pages ins Web geteilt, mit Sensitive-Keyword-Scan im Titel | HIGH–CRITICAL | DSGVO Art. 32, SOC 2 CC6.1, ISO 27001 A.5.10 |
| **Orphaned Pages** — Database-Einträge ohne zugewiesenen Owner | MEDIUM | ISO 27001 A.5.2, SOC 2 CC1.3 |
| **Stale Data** — Pages, seit über 365 Tagen nicht editiert | LOW–MEDIUM | DSGVO Art. 5(1)(d), ISO 27001 A.5.34 |
| **PII Exposure** — Plaintext Kreditkarten (Luhn-validiert), IBANs (mod-97-validiert), Steuer-IDs, US SSN, eingebettete Passwörter & API-Keys | HIGH–CRITICAL | DSGVO Art. 9, Art. 32, PCI-DSS Req 3.4 |

Compliance-Score 0–100, gewichtet nach Severity. Bei einem Audit, der auf API-Errors stößt, gibt's `N/A` statt eines irreführenden 100/100. Hat seinen Grund — siehe weiter unten.

---

## Warum so gebaut, und nicht anders

**Slash Command war die erste Idee.** `/ncc` in eine Page tippen, Audit kommt zurück. Hab die Notion-API-Doku gelesen und gemerkt: Slash Commands sind aktuell kein öffentlicher Extension-Point. Das war der Moment, an dem das Projekt entweder pivotet oder peinlich endet.

**Pivot zu MCP + Webhook.** Weil das die zwei Wege sind, die Notion *tatsächlich* ausbaut. MCP-Server sieht aus wie wo die Plattform hingeht. Webhook-Buttons existieren seit ~2024 und decken den "ein Klick"-Use-Case ab, ohne Middleware-Pseudo-Lösungen.

**Async + httpx, nicht das offizielle Notion-SDK.** Das offizielle Python-SDK ist sync-only. Bei meinem Workspace mit ein paar hundert Pages dauert das spürbar. Mit `asyncio.gather` über die vier Checks und einem Semaphore-bounded Page-Scan im PII-Check läuft der ganze Audit unter ~5 Sekunden.

**Luhn + mod-97 für PII, nicht nur Regex.** Eine Regex matcht jede 16-stellige Zahl, also auch jede 16-stellige Bestellnummer. Eine echte Kreditkartennummer muss aber die Luhn-Prüfsumme erfüllen, eine echte IBAN den mod-97-Check. Tests haben aufgedeckt, dass `0000 0000 0000 0000` mathematisch durch Luhn kommt — also Extra-Guard rein, dass Karten nicht mit Null anfangen. Das sind die Details, die den Unterschied zwischen einer rauschigen Spreadsheet-Ausgabe und einem auditfähigen Signal machen.

**Shared Secret im Webhook-Body** statt Header — Notions native Webhook-Action unterstützt keine Custom-Header. Workaround mit `hmac.compare_digest`. Wird ersetzt, sobald Notion signierte Webhooks ausrollt.

---

## Was beim Bauen rausgekommen ist

Drei kleine Geschichten, die's wert sind, sie zu erzählen.

**1. Tests sind keine Coverage-Theater.** Mein erster IBAN-Regex hat `DE89 3704 0044 0532 0130 00` nicht gematcht — der Real-World-Format mit Spaces zwischen 4-Stellen-Gruppen war im Pattern nicht abgebildet. Aufgefallen weil ich mit echten Test-IBANs aus dem Notion-Wikipedia-Beispiel getestet hab, nicht mit "DE12345…". Der zweite Bug: Luhn akzeptierte `0000…0000`. Mathematisch korrekt, real Quatsch. Beide nur durch Tests gefangen.

**2. Mein eigenes Tool hat sich beim Bauen erwischt.** GitHub Secret Scanning hat einen Stripe-Test-Key in meinem Demo-Material blockiert — den offiziellen Test-Key aus Stripes eigener Doku. Pattern-Matching kann nicht zwischen "echtem Secret" und "öffentlichem Test-Wert" unterscheiden. Genau die Art False-Positive-Tradeoff, die ich auch in NCCs PII-Check abwäge. Schöne Meta-Erinnerung warum strukturelle Validierung wichtig ist.

**3. Score-Bug live entdeckt.** Beim ersten echten Audit hat mein Token nicht gegriffen — alle vier Checks haben mit 401 gefailt, null Findings, Score zeigte fröhlich **100/100**. Sah aus wie ein perfekter Workspace, war aber ein vollständig stiller Fehler. Sofortiger Fix: Score liefert jetzt `None` / „N/A" wenn irgendein Check geraised hat. Plus Regression-Test. Die Art Bug, die nur entstehen kann, wenn man das eigene Tool tatsächlich gegen echte Daten laufen lässt — nicht gegen Mocks.

---

## Was ich noch bauen würde

- **Sharing-Graph-Diff** — heutigen Permission-Graph mit dem von letzter Woche vergleichen. Compliance-Regressionen sind meistens inkrementell; Snapshots fangen das nicht.
- **External-Guest-Audit** — Pages flaggen, die mit E-Mail-Domains außerhalb der Org geteilt sind.
- **Custom Checks via YAML-DSL** — Compliance-Officers schreiben Regeln, statt darauf zu warten, dass jemand Python kann.
- **Reaktion auf Notions Workspace-Webhooks** — neue öffentliche Pages sofort scannen, statt erst beim nächsten Audit. Watchdog statt Snapshot.
- **PII auf gerendertem Text, nicht Raw-Blocks.** Eine IBAN, die durch einen Bold-Style aufgeteilt wird, würde aktuell verpasst. Lösung: Block zu normalisiertem String rendern, dann scannen.

---

Kein Marketing, kein Trial-Account, kein Sales-Pitch. Repo ist offen, Code ist MIT, Issues sind willkommen.

[github.com/BlackBeautyxSurferboy/notion-compliance-check](https://github.com/BlackBeautyxSurferboy/notion-compliance-check)
