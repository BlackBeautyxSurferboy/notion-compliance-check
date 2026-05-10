# Test-Sandbox-Setup für die NCC-Demo

Damit der Audit beim Demo-Run nicht leer läuft, lohnt es sich, gezielt "Schmutz" zu erzeugen — Inhalte, die genau die vier Checks triggern. Diese Datei beschreibt das komplette Setup für eine vorzeigbare Demo.

> ⚠ Alle PII-Werte unten sind **bekannte öffentliche Test-Werte** — keine echten Karten, IBANs oder Geheimnisse. Sie sind in keinem Payment-System gültig.

## Zielbild

Nach dem Setup sollte ein `ncc audit` mindestens je einen Treffer in jeder Severity-Stufe (CRITICAL / HIGH / MEDIUM / LOW) liefern und einen Compliance-Score von etwa 40–60 produzieren.

| Check | Triggern durch |
|---|---|
| `public_access` | Eine public geteilte Page mit sensitivem Titel |
| `pii_exposure` | Page-Inhalte mit Visa, IBAN, API-Key |
| `orphaned_pages` | Database-Eintrag ohne zugewiesenen Owner |
| `stale_data` | Wird automatisch durch ältere Pages im Workspace getroffen — kein Setup nötig |

---

## Page 1 — "NCC Test-Sandbox"

Lege eine neue Page an mit Titel `NCC Test-Sandbox` (oder direkt unter deinem Compliance-Reports-Parent). Inhalt zum Reinkopieren steht in [`test-sandbox-content.md`](./test-sandbox-content.md). Diese Page muss **nicht** geteilt werden — sie triggert nur den `pii_exposure`-Check.

## Page 2 — "Q3 Finanzen — vertraulich" (CRITICAL)

1. Neue Page anlegen mit dem genauen Titel: **`Q3 Finanzen — vertraulich`**
2. Beliebigen Inhalt rein (1–2 Sätze reichen)
3. Oben rechts auf **Teilen** → **Im Web veröffentlichen** aktivieren
4. **Wichtig**: NCC-Integration auch zu dieser Page connecten (`...` → `Verbindungen` → NCC)

Der Audit findet das als CRITICAL: öffentliche Page **plus** sensitives Keyword im Titel ("Finanzen", "vertraulich").

## Database 3 — "Risiko-Register" (MEDIUM)

1. Neue Database anlegen mit Titel `Risiko-Register`
2. Properties:
   - `Name` (Title)
   - `Verantwortlich` (People)  ← Property-Name muss exakt diesen Namen haben (oder "Owner")
   - `Risiko-Level` (Select: Low/Medium/High)
3. Drei Beispiel-Einträge anlegen:
   - "Datenleck-Notfallplan" → Verantwortlich: dich selbst zuweisen
   - "DSGVO-Auskunftsersuchen-Prozess" → Verantwortlich: dich selbst
   - "Dienstleister-Audit Cloudflare" → **Verantwortlich leer lassen** ← das ist der Trigger
4. NCC-Integration zur Database connecten

Der Audit findet den dritten Eintrag als orphaned page (MEDIUM, ISO 27001 A.5.2).

## Page 4+ — Stale Data (LOW)

Wahrscheinlich nichts zu tun. Wenn dein Workspace seit über einem Jahr existiert, gibt es vermutlich Pages, die seit über 365 Tagen nicht angefasst wurden — die werden automatisch gefunden.

Falls dein Workspace zu neu ist und du auch diesen Check triggern willst:
- Setze für den Demo-Run den Schwellwert runter, z.B. `NCC_STALE_THRESHOLD_DAYS=30` in der `.env`. Dann werden Pages älter als 30 Tage geflaggt.

---

## Einmalige Verbindungen

Vergiss nicht, die NCC-Integration mit allen vier oben genannten Containern zu verbinden:
- Page 1 (Test-Sandbox)
- Page 2 (Q3 Finanzen)
- Database 3 (Risiko-Register)
- Die Parent-Page für die Reports (NCC_REPORT_PARENT_PAGE_ID)

Pro Container einmal: `...` (Menü) → `Verbindungen` → `NCC - Compliance Check`.

## Test-Run

```bash
cd /Users/alex/Desktop/Notion/notion-compliance-check
source .venv/bin/activate
ncc audit                # Tabelle im Terminal — sollte 4+ Findings zeigen
ncc audit --post         # Report-Page in Notion erzeugen
```
