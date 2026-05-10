# NCC Test-Sandbox

Diese Seite enthält absichtlich problematische Inhalte für den Compliance-Audit. Bitte nicht aus Versehen teilen oder als Vorlage verwenden — sämtliche Werte unten sind öffentliche Test-Daten ohne reale Funktion.

## Onboarding-Checkliste neuer Mitarbeitende

Hier sammle ich die wichtigsten Schritte für unser Onboarding. Aktuell läuft das noch sehr manuell — Verbesserungsvorschläge willkommen.

- Begrüßungsmail rausschicken
- Hardware-Bestellung freigeben
- Slack- und Notion-Zugänge anlegen
- Vertragsdaten ans Lohnbüro: Überweisung an die Test-IBAN **DE89 3704 0044 0532 0130 00** (Bank: Commerzbank Berlin)
- Schulungsunterlagen verschicken

## Reisekostenerstattung Q2

Für Vorabbuchungen bitte folgende Firmenkarte verwenden:

- Karteninhaber: Acme GmbH Reisekonto
- Kartennummer: 4539 1488 0343 6467
- Gültig bis: 12/2027
- CVC: 123

Bei Fragen zur Buchhaltung bitte direkt an Finance wenden.

## Deploy-Runbook (Staging)

Für den Notfall — falls niemand aus DevOps erreichbar ist:

```
ssh deploy@staging.example.com
cd /var/www/app
export DB_USER=admin
export DB_PASSWORD=hunter2_supersecret
export PAYMENT_API_KEY=demo_FAKE_KEY_NOT_REAL_abc123XYZdef
./deploy.sh --env=staging
```

> Bitte das hier nicht in Slack rumschicken. (Anmerkung der Redaktion: Genau deshalb checkt NCC sowas.)

## Kunden-Notizen — Acme Corp

Hauptansprechpartner ist Markus Schmidt, persönliche Steuer-ID **12345678901** (für die Erstattung des letzten Quartals). Bezahlung läuft über die IBAN **GB82 WEST 1234 5698 7654 32**.

## Offene Punkte

- [ ] Datenschutzerklärung an die neue DSGVO-Auslegung anpassen
- [ ] Externe Auditoren-Zugriff auf Q3-Finanzdokumente klären
- [ ] Passwort-Policy review (siehe Deploy-Runbook oben — der Approach ist nicht skalierbar)
- [ ] Mitarbeiterperformance-Review-Prozess dokumentieren

---

*Letzte Aktualisierung: heute. Diese Page ist eine **Test-Sandbox** für das NCC-Compliance-Tool — alle PII-Werte sind öffentliche Test-Werte ohne reale Gültigkeit.*
