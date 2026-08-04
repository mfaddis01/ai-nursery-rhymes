"""Tests for TTS quota reporting.

ElevenLabs is the metered dependency: 10,000 characters a month on the free
tier, several hundred per rhyme. When it runs out, generation stops while the
rest of the pipeline still reports success — which is exactly what happened on
2026-08-04, when the batch produced 0 videos with 37 characters remaining.

The properties that matter here are that the numbers are right, that a low
balance is called out rather than buried, and above all that a credits lookup
can never take the batch down with it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import credits  # noqa: E402


def _sub(used: int, limit: int = 10_000, tier: str = "free") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "character_count": used,
        "character_limit": limit,
        "tier": tier,
        "next_character_count_reset_unix": 1787555173,
    }
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")


class TestQuota:
    def test_reports_remaining_and_percentage(self):
        with patch("requests.get", return_value=_sub(used=2_500)):
            q = credits.elevenlabs_quota()
        assert q["remaining"] == 7_500
        assert q["pct_remaining"] == pytest.approx(75.0)
        assert q["low"] is False

    def test_flags_a_low_balance(self):
        """The 2026-08-04 state: 37 characters left, not enough for a rhyme."""
        with patch("requests.get", return_value=_sub(used=9_963)):
            q = credits.elevenlabs_quota()
        assert q["remaining"] == 37
        assert q["low"] is True

    def test_never_reports_negative_remaining(self):
        """Overage must read as 0 left, not a negative balance."""
        with patch("requests.get", return_value=_sub(used=12_000)):
            assert credits.elevenlabs_quota()["remaining"] == 0

    def test_missing_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        assert credits.elevenlabs_quota() is None

    @pytest.mark.parametrize("failure", [
        requests.ConnectionError("down"),
        requests.Timeout("slow"),
        ValueError("not json"),
    ])
    def test_failures_return_none_and_never_raise(self, failure):
        """A credits display is worth less than a batch run."""
        with patch("requests.get", side_effect=failure):
            assert credits.elevenlabs_quota() is None

    def test_schema_drift_returns_none(self):
        resp = MagicMock()
        resp.json.return_value = {"unexpected": "shape"}
        resp.raise_for_status.return_value = None
        with patch("requests.get", return_value=resp):
            assert credits.elevenlabs_quota() is None

    def test_zero_limit_does_not_divide_by_zero(self):
        with patch("requests.get", return_value=_sub(used=0, limit=0)):
            assert credits.elevenlabs_quota()["pct_remaining"] == 0.0


class TestFormatting:
    def test_healthy_balance_has_no_warning(self):
        with patch("requests.get", return_value=_sub(used=2_500)):
            line = credits.format_credits_line(credits.elevenlabs_quota())
        assert "7,500" in line and "⚠️" not in line

    def test_low_balance_warns_and_explains(self):
        with patch("requests.get", return_value=_sub(used=9_963)):
            line = credits.format_credits_line(credits.elevenlabs_quota())
        assert "⚠️" in line
        assert "TTS will fail" in line

    def test_unavailable_quota_says_so(self):
        line = credits.format_credits_line(None)
        assert "unavailable" in line
