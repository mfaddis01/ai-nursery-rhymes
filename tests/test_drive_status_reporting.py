"""Tests for the Google Drive line in the daily notification.

The notification is the only channel that tells the operator what a run
actually did with Drive, so every state it can report has to be true.

Two states were being misreported. A run that produced nothing had nothing to
mirror, but the summary still read "✗ Google Drive: 0 of 0 file(s) uploaded" --
a failure invented out of an empty batch, printed right next to the real reason
the batch was empty. And when Drive is configured but its credentials have
expired (the host's ADC needs a periodic re-login), the same line blamed the
uploads and pointed at `sync-drive`, which refuses to run without credentials.
The credential problem only ever appeared in the journal.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import credits  # noqa: E402


def _quota(remaining: int = 7_500, limit: int = 10_000) -> dict:
    return {
        "used": limit - remaining,
        "limit": limit,
        "remaining": remaining,
        "pct_remaining": remaining / limit * 100,
        "tier": "free",
        "resets_unix": 1787555173,
        "low": remaining < credits.LOW_CHARACTER_THRESHOLD,
    }


@pytest.fixture
def notifier(monkeypatch, tmp_path):
    """A DailyScheduler with the real _notify_videos_ready, writing to tmp_path.

    The notification path is './notifications/...' relative to the cwd, so
    without the chdir these tests would litter the repo.
    """
    import daily_scheduler

    with patch.object(daily_scheduler, "RhymeManager"), \
         patch.object(daily_scheduler, "VideoGenerator"), \
         patch.object(daily_scheduler, "UploadQueue"), \
         patch.object(daily_scheduler, "DriveSync"), \
         patch.object(daily_scheduler, "BackgroundScheduler"):
        sched = daily_scheduler.DailyScheduler()

    monkeypatch.chdir(tmp_path)
    sched.upload_queue.get_queue_summary.return_value = {"pending_videos": 74}
    return sched


def _message(scheduler, videos, drive_uploaded):
    """Run the real notifier and return the message it sent."""
    import daily_scheduler

    with patch.object(credits, "elevenlabs_quota", return_value=_quota()), \
         patch.object(daily_scheduler.notify, "send_telegram", return_value=True) as send:
        scheduler._notify_videos_ready(videos, drive_uploaded)

    return send.call_args.args[0]


def _videos(count: int, shorts_each: int = 2) -> list:
    return [
        {"title": f"Rhyme {i}", "rhyme_id": f"r{i}", "short_count": shorts_each}
        for i in range(count)
    ]


class TestDriveNotConfigured:
    def test_says_so_and_claims_no_failure(self, notifier):
        notifier.drive_sync = None
        message = _message(notifier, [], 0)

        assert "Google Drive not configured." in message
        assert "✗" not in message


class TestDriveCredentialsExpired:
    """Today's host state: folder id set, so DriveSync exists, but its
    authentication failed, so `service` is None."""

    @pytest.fixture
    def notifier(self, notifier):
        notifier.drive_sync = MagicMock()
        notifier.drive_sync.is_authenticated.return_value = False
        return notifier

    def test_names_the_credential_problem(self, notifier):
        message = _message(notifier, [], 0)

        assert "not authenticated" in message
        assert "gcloud auth application-default login" in message

    def test_does_not_blame_the_uploads(self, notifier):
        """`sync-drive` refuses to run without credentials, so offering it as
        the only remedy sends the operator down a dead end."""
        message = _message(notifier, [], 0)

        assert "0 of 0" not in message
        assert "✗" not in message

    def test_reported_even_when_the_batch_produced_videos(self, notifier):
        """A successful batch whose mirror silently did nothing is exactly the
        case that must not read as healthy."""
        message = _message(notifier, _videos(2), 0)

        assert "not authenticated" in message
        assert "✓ All" not in message


class TestDriveHealthy:
    @pytest.fixture
    def notifier(self, notifier):
        notifier.drive_sync = MagicMock()
        notifier.drive_sync.is_authenticated.return_value = True
        return notifier

    def test_empty_batch_invents_no_failure(self, notifier):
        """Nothing was generated, so nothing was owed to Drive."""
        message = _message(notifier, [], 0)

        assert "nothing to upload" in message
        assert "0 of 0" not in message
        assert "✗" not in message

    def test_full_upload_reports_success(self, notifier):
        message = _message(notifier, _videos(2), 6)

        assert "✓ All 6 file(s) uploaded" in message
        assert "✗" not in message

    def test_partial_upload_still_reports_failure(self, notifier):
        """The original bug this line was written for: a run where uploads
        genuinely failed must not read as healthy."""
        message = _message(notifier, _videos(2), 4)

        assert "✗ Google Drive: 4 of 6 file(s) uploaded" in message
        assert "sync-drive" in message

    def test_zero_of_many_is_a_failure_not_an_empty_batch(self, notifier):
        message = _message(notifier, _videos(2), 0)

        assert "✗ Google Drive: 0 of 6 file(s) uploaded" in message
