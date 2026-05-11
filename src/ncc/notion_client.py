"""Thin async wrapper around the Notion REST API.

We intentionally call the API directly with httpx instead of the official
notion-client SDK — the SDK is sync-only at the time of writing, and an async
implementation lets us parallelise checks across hundreds of pages.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionAPIError(RuntimeError):
    """Raised when the Notion API returns a non-2xx response."""


class NotionClient:
    def __init__(self, token: str, *, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=NOTION_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def __aenter__(self) -> NotionClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        for attempt in range(3):
            response = await self._client.request(method, path, **kwargs)
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
                await asyncio.sleep(retry_after * (attempt + 1))
                continue
            if response.is_error:
                raise NotionAPIError(
                    f"Notion API {method} {path} -> {response.status_code}: {response.text}"
                )
            return response.json()
        raise NotionAPIError(f"Notion API {method} {path} -> still 429 after retries")

    async def search(
        self,
        *,
        query: str | None = None,
        filter_object: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield every page/database the integration has access to."""
        body: dict[str, Any] = {"page_size": 100}
        if query is not None:
            body["query"] = query
        if filter_object is not None:
            body["filter"] = {"property": "object", "value": filter_object}

        cursor: str | None = None
        while True:
            payload = {**body}
            if cursor:
                payload["start_cursor"] = cursor
            data = await self._request("POST", "/search", json=payload)
            for item in data.get("results", []):
                yield item
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")

    async def query_database(self, database_id: str) -> AsyncIterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = await self._request(
                "POST", f"/databases/{database_id}/query", json=payload
            )
            for item in data.get("results", []):
                yield item
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")

    async def retrieve_block_children(self, block_id: str) -> AsyncIterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = await self._request(
                "GET", f"/blocks/{block_id}/children", params=params
            )
            for item in data.get("results", []):
                yield item
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")

    async def retrieve_database(self, database_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/databases/{database_id}")

    async def create_page(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/pages", json=body)

    async def update_page(self, page_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"/pages/{page_id}", json=body)

    async def append_block_children(
        self, block_id: str, children: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH", f"/blocks/{block_id}/children", json={"children": children}
        )

    async def create_database(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/databases", json=body)

    async def archive_page(self, page_id: str) -> dict[str, Any]:
        """Soft-delete a page (Notion's 'archive'). Reversible via the UI trash."""
        return await self._request(
            "PATCH", f"/pages/{page_id}", json={"archived": True}
        )

    async def archive_database(self, database_id: str) -> dict[str, Any]:
        return await self._request(
            "PATCH", f"/databases/{database_id}", json={"archived": True}
        )


def page_title(page: dict[str, Any]) -> str:
    """Best-effort extraction of a human-readable title from a page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts) or "(untitled)"
    return "(untitled)"


def page_url(page: dict[str, Any]) -> str:
    return page.get("url", "")
