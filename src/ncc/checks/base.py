"""Base types every compliance check shares."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ncc.notion_client import NotionClient


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def emoji(self) -> str:
        return {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🔵",
            Severity.INFO: "⚪",
        }[self]

    @property
    def callout_color(self) -> str:
        # Notion API "color" values for callout blocks
        return {
            Severity.CRITICAL: "red_background",
            Severity.HIGH: "orange_background",
            Severity.MEDIUM: "yellow_background",
            Severity.LOW: "blue_background",
            Severity.INFO: "gray_background",
        }[self]


@dataclass(slots=True)
class Finding:
    check_id: str
    severity: Severity
    title: str
    detail: str
    page_id: str | None = None
    page_url: str | None = None
    page_title: str | None = None
    framework_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "page_id": self.page_id,
            "page_url": self.page_url,
            "page_title": self.page_title,
            "framework_refs": self.framework_refs,
        }


class Check(ABC):
    """A single compliance check. Subclasses implement `run`."""

    id: str
    name: str
    description: str

    @abstractmethod
    async def run(self, client: NotionClient) -> list[Finding]: ...
