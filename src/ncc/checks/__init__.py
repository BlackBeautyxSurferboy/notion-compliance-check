"""Compliance checks. Each check returns a list of Findings."""

from ncc.checks.base import Check, Finding, Severity
from ncc.checks.orphaned_pages import OrphanedPagesCheck
from ncc.checks.pii import PIIExposureCheck
from ncc.checks.public_access import PublicAccessCheck
from ncc.checks.stale_data import StaleDataCheck

ALL_CHECKS: list[type[Check]] = [
    PublicAccessCheck,
    OrphanedPagesCheck,
    StaleDataCheck,
    PIIExposureCheck,
]

__all__ = [
    "ALL_CHECKS",
    "Check",
    "Finding",
    "OrphanedPagesCheck",
    "PIIExposureCheck",
    "PublicAccessCheck",
    "Severity",
    "StaleDataCheck",
]
