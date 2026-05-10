# NCC Test-Sandbox

Diese Seite enthält absichtlich problematische Inhalte für den Compliance-Audit. Bitte nicht aus Versehen teilen oder als Vorlage verwenden — sämtliche Werte unten sind öffentliche Test-Daten ohne reale Funktion.

## Onboarding neuer Mitarbeitende — Checkliste

Hier sammle ich die wichtigsten Schritte für unser Onboarding. Aktuell läuft das noch sehr manuell — Verbesserungsvorschläge willkommen.

- Begrüßungsmail rausschicken
- Hardware-Bestellung freigeben (MacBook Pro M4, externer Monitor)
- Slack- und Notion-Zugänge anlegen
- Vertragsdaten ans Lohnbüro: Überweisung an die Test-IBAN **DE89 3704 0044 0532 0130 00** (Bank: Commerzbank Berlin)
- Steuerliche Daten: Steuer-ID des Mitarbeiters muss übermittelt werden — bei letztem Onboarding war das **12345678901**
- Schulungsunterlagen verschicken
- Erste Probezeit-Review nach 30 Tagen einplanen

## Reisekostenerstattung — Q2

Für Vorabbuchungen bitte die folgende Firmenkarte verwenden. Anfrage und Originalbelege gehen anschließend an die Buchhaltung.

- **Karteninhaber:** Acme GmbH Reisekonto
- **Kartennummer:** 4539 1488 0343 6467
- **Gültig bis:** 12 / 2027
- **CVC:** 123
- **Verfügungsrahmen:** 5.000 € pro Reise

Bei Auslandsreisen nach UK bitte stattdessen das UK-Konto nutzen: **GB82 WEST 1234 5698 7654 32**.

## Deploy-Runbook (Staging)

Quick-Reference für den Notfall — falls niemand aus DevOps erreichbar ist und der Staging-Build schief geht.

```
ssh deploy@staging.acme.example
cd /var/www/app
export DB_USER=admin
export DB_PASSWORD=hunter2_supersecret
export PAYMENT_API_KEY=demo_FAKE_KEY_NOT_REAL_abc123XYZdef
./deploy.sh --env=staging
```

> Bitte das hier nicht in Slack rumschicken. (Anmerkung der Redaktion: Genau deshalb checkt NCC sowas.)

Wenn der Deploy fehlschlägt, ist der häufigste Grund ein abgelaufenes Cert. Logs liegen unter `/var/log/acme/deploy.log`.

## Kunden-Notizen — Schmidt Industries GmbH

Hauptansprechpartner ist **Markus Schmidt**, Geschäftsführer. Persönliche Steuer-ID **23456789012** (für die Erstattung des letzten Quartals — bitte nicht weiterleiten). Bezahlung läuft über die IBAN **FR14 2004 1010 0505 0001 3M02 606**.

Kontostand-Auszug Q1 / 2026: 47.230 €. Nächste Rechnung wird Mitte des Monats fällig.

Notiz: Markus hat im letzten Call angedeutet, dass sein Vater (Inhaber) die Firma in 2027 verkaufen will — vertraulich behandeln.

## Lieferantenliste — Daten-Dienstleister

| Anbieter | Vertrag | IBAN | Status |
|---|---|---|---|
| Cloudflare GmbH | seit 2023 | DE19 1001 0010 0987 6543 21 | aktiv |
| Sentry Inc. | seit 2024 | (USD-Konto, keine IBAN) | aktiv |
| Datadog Germany | seit 2025 | DE45 5001 0517 0123 4567 89 | in Verhandlung |

Alle drei Verträge müssten unter DSGVO Art. 28 geprüft sein (Auftragsverarbeitungs-Vereinbarung). Cloudflare ist sicher, Sentry und Datadog muss ich nochmal nachhaken.

## Offene Punkte / TODO

- [ ] Datenschutzerklärung an die neue DSGVO-Auslegung anpassen (Termin Ende Mai)
- [ ] Externe Auditoren-Zugriff auf Q3-Finanzdokumente klären — die wollen Read-Only bis Ende Juni
- [ ] Passwort-Policy review (siehe Deploy-Runbook oben — der Approach mit Klartext-Variablen ist nicht skalierbar)
- [ ] Mitarbeiterperformance-Review-Prozess dokumentieren
- [ ] AVV-Templates für die drei Lieferanten oben gegenchecken
- [ ] Diese Sandbox-Page nach der Demo aufräumen oder löschen 🙄

## Notizen aus dem Compliance-Workshop (April)

War ein langer Tag. Wichtigste Take-Aways:

> "Der größte Risikofaktor in deutschen Mid-Caps ist nicht der externe Angreifer, sondern die unbeabsichtigte interne Daten-Exposure durch Tool-Sprawl." — Vortragender, der seinen Namen nicht in einem Deck sehen wollte

Konkrete Folgerungen:
1. Tool-Inventory machen (welche SaaS-Lösungen haben tatsächlich Zugriff auf personenbezogene Daten?)
2. Sharing-Permissions in jeder Plattform reviewen — ist die schwierigste, weil pro Tool anders
3. Regelmäßige Audits, nicht nur Snapshots

Punkt 2 und 3 sind so schwer, dass die meisten Firmen es schlichtweg nicht machen. Gefühlt 80% Compliance-Theater, 20% echter Schutz.

---

*Test-Sandbox für das NCC-Compliance-Tool — alle Werte sind öffentliche Test-Werte ohne reale Gültigkeit. Echte personenbezogene Daten gehören nicht in diese Page.*
