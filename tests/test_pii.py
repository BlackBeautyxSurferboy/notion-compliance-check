"""PII detection: validators must reject random digit strings, accept real values."""

from __future__ import annotations

import pytest

from ncc.checks.pii import _iban_valid, _luhn_valid, find_pii


class TestLuhn:
    @pytest.mark.parametrize("number", [
        "4539 1488 0343 6467",  # Visa test number, valid Luhn
        "5500-0000-0000-0004",  # Mastercard test number
        "340000000000009",      # Amex test number
    ])
    def test_valid_card_numbers(self, number: str) -> None:
        assert _luhn_valid(number) is True

    @pytest.mark.parametrize("number", [
        "1234 5678 9012 3456",
        "0000 0000 0000 0000",
        "9999999999999999",
    ])
    def test_invalid_card_numbers(self, number: str) -> None:
        assert _luhn_valid(number) is False


class TestIBAN:
    @pytest.mark.parametrize("iban", [
        "DE89 3704 0044 0532 0130 00",  # German example IBAN, valid checksum
        "GB82WEST12345698765432",        # UK example IBAN
        "FR1420041010050500013M02606",   # French example IBAN
    ])
    def test_valid_iban(self, iban: str) -> None:
        assert _iban_valid(iban) is True

    @pytest.mark.parametrize("iban", [
        "DE00 0000 0000 0000 0000 00",
        "XX12 3456 7890 1234 5678 90",
        "DE99 3704 0044 0532 0130 00",  # broken checksum
    ])
    def test_invalid_iban(self, iban: str) -> None:
        assert _iban_valid(iban) is False


class TestFindPII:
    def test_detects_credit_card(self) -> None:
        text = "My card is 4539 1488 0343 6467 — please don't share."
        matches = find_pii(text)
        assert any(p.name == "credit_card" for p, _ in matches)

    def test_ignores_invalid_card(self) -> None:
        text = "Random digits: 1234 5678 9012 3456"
        matches = find_pii(text)
        assert not any(p.name == "credit_card" for p, _ in matches)

    def test_detects_iban(self) -> None:
        text = "Wire to DE89 3704 0044 0532 0130 00 by Friday."
        matches = find_pii(text)
        assert any(p.name == "iban" for p, _ in matches)

    def test_detects_password_assignment(self) -> None:
        text = "config.password = hunter2_supersecret"
        matches = find_pii(text)
        assert any(p.name == "email_with_password_context" for p, _ in matches)

    def test_detects_api_key(self) -> None:
        text = "API_KEY=sk_live_abcdef1234567890XYZ"
        matches = find_pii(text)
        assert any(p.name == "email_with_password_context" for p, _ in matches)

    def test_clean_text_returns_no_findings(self) -> None:
        text = "This is a perfectly normal meeting note about Q4 planning."
        assert find_pii(text) == []
