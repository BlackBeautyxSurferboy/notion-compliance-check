"""Smoke tests for the FastAPI app: routes mounted, auth enforced, widget renders."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Force env values before importing the app so load_dotenv(override=True)
    # cannot resurrect a stale local .env.
    monkeypatch.setenv("NCC_WEBHOOK_SECRET", "test-secret-12345")
    monkeypatch.setenv("NOTION_TOKEN", "ntn_dummy_token_for_tests_only")
    monkeypatch.setenv("NCC_REPORT_PARENT_PAGE_ID", "deadbeefdeadbeefdeadbeefdeadbeef")
    monkeypatch.delenv("NCC_HISTORY_DB_ID", raising=False)

    # Late import so env vars are picked up
    from ncc.webhook import app
    return TestClient(app)


def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_widget_returns_html(client: TestClient) -> None:
    r = client.get("/widget")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "NCC Compliance" in body
    assert "Run Compliance Audit" in body or "Read-only" in body


def test_widget_without_key_is_read_only(client: TestClient) -> None:
    r = client.get("/widget")
    assert "true" not in _extract_can_trigger(r.text)


def test_widget_with_correct_key_can_trigger(client: TestClient) -> None:
    r = client.get("/widget?key=test-secret-12345")
    assert "true" in _extract_can_trigger(r.text)


def test_widget_with_wrong_key_is_read_only(client: TestClient) -> None:
    r = client.get("/widget?key=wrong-key")
    assert "false" in _extract_can_trigger(r.text)


def test_api_trigger_requires_correct_key(client: TestClient) -> None:
    r = client.post("/api/audit/trigger?key=wrong-key")
    assert r.status_code == 401


def test_webhook_requires_header_auth(client: TestClient) -> None:
    r = client.post("/webhook/run-audit", json={})
    assert r.status_code == 401


def test_webhook_accepts_header_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stub out the background audit so the test doesn't hit Notion.
    async def _stub(*args: object, **kwargs: object) -> None:
        return None
    monkeypatch.setattr("ncc.webhook._run_and_post", _stub)

    r = client.post(
        "/webhook/run-audit",
        headers={"X-NCC-Secret": "test-secret-12345"},
        json={},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


def test_webhook_accepts_bearer_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _stub(*args: object, **kwargs: object) -> None:
        return None
    monkeypatch.setattr("ncc.webhook._run_and_post", _stub)

    r = client.post(
        "/webhook/run-audit",
        headers={"Authorization": "Bearer test-secret-12345"},
        json={},
    )
    assert r.status_code == 200


def test_api_status_unknown_job_returns_404(client: TestClient) -> None:
    r = client.get("/api/audit/status/nonexistent-job-id")
    assert r.status_code == 404


def test_api_latest_returns_unavailable_when_no_db(client: TestClient) -> None:
    r = client.get("/api/audit/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False


def test_api_history_returns_empty_when_no_db(client: TestClient) -> None:
    r = client.get("/api/audit/history")
    assert r.status_code == 200
    assert r.json() == {"rows": []}


def _extract_can_trigger(html: str) -> str:
    """Pluck the CAN_TRIGGER replacement out of the widget HTML."""
    marker = 'CAN_TRIGGER = (("'
    if marker not in html:
        return ""
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]
