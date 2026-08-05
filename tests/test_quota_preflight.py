"""Tests for the TTS quota pre-flight that guards a batch.

On 2026-08-04 and again on 2026-08-05 the daily unit failed with 0 videos and
37 of 10,000 ElevenLabs characters left. The quota being empty is not a bug —
the batch genuinely cannot run. What was a bug is *when* the pipeline found
out: TTS is the first step of every video, but the quota was only read at the
end, for the notification. So every doomed run first shelled out to the Claude
CLI for each AI slot and saved those rhymes to disk (generate_new_rhyme saves
before TTS is ever attempted), orphaning rhymes that never become videos and
that then crowd out later ones through the "these already exist" list.

The properties pinned here: an impossible batch spends nothing, an unreadable
quota never blocks a batch, a sufficient quota is left completely alone, and
the failure stays loud in every case.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import credits  # noqa: E402


def _quota(remaining: int, limit: int = 10_000) -> dict:
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
def scheduler():
    """A DailyScheduler with every outbound dependency stubbed."""
    import daily_scheduler

    with patch.object(daily_scheduler, "RhymeManager"), \
         patch.object(daily_scheduler, "VideoGenerator"), \
         patch.object(daily_scheduler, "UploadQueue"), \
         patch.object(daily_scheduler, "DriveSync"), \
         patch.object(daily_scheduler, "BackgroundScheduler"):
        sched = daily_scheduler.DailyScheduler()

    sched.videos_per_day = 5
    sched.drive_sync = None
    sched._notify_videos_ready = MagicMock()
    return sched


@pytest.fixture
def real_notifier(scheduler, monkeypatch, tmp_path):
    """Restore the real _notify_videos_ready, writing its JSON under tmp_path.

    The notification path is './notifications/...' relative to the cwd, so
    without the chdir these tests would litter the repo.
    """
    monkeypatch.chdir(tmp_path)
    del scheduler._notify_videos_ready  # unshadow the class method
    scheduler.upload_queue.get_queue_summary.return_value = {"pending_videos": 74}
    return scheduler


class TestCanGenerate:
    def test_empty_quota_cannot_generate(self):
        """The 2026-08-05 state: 37 characters, a rhyme needs several hundred."""
        assert credits.can_generate(_quota(37)) is False

    def test_exhausted_quota_cannot_generate(self):
        assert credits.can_generate(_quota(0)) is False

    def test_unreadable_quota_is_treated_as_usable(self):
        """A credits lookup must never be the reason a batch does not run."""
        assert credits.can_generate(None) is True

    def test_healthy_quota_can_generate(self):
        assert credits.can_generate(_quota(7_500)) is True

    def test_low_but_usable_quota_still_generates(self):
        """`low` warns the operator; it must not veto a batch that can still
        produce videos. 900 characters is two short rhymes."""
        q = _quota(900)
        assert q["low"] is True
        assert credits.can_generate(q) is True

    def test_boundary_is_inclusive(self):
        assert credits.can_generate(_quota(credits.MIN_RHYME_CHARACTERS)) is True
        assert credits.can_generate(_quota(credits.MIN_RHYME_CHARACTERS - 1)) is False


class TestPreflightBlocksAnImpossibleBatch:
    def test_spends_no_claude_calls_and_writes_no_rhymes(self, scheduler):
        """The whole point: an impossible batch must cost nothing."""
        with patch.object(credits, "elevenlabs_quota", return_value=_quota(37)):
            produced = scheduler.generate_daily_videos()

        assert produced == 0
        scheduler.rhyme_manager.generate_new_rhyme.assert_not_called()
        scheduler.video_generator.generate_long_form_video.assert_not_called()
        scheduler.upload_queue.add_video_pair.assert_not_called()

    def test_still_returns_zero_so_the_unit_fails_visibly(self, scheduler):
        """Failing fast must not become failing silently: run_daily.py turns a
        0 into exit 1, which is what makes systemd flag the unit."""
        with patch.object(credits, "elevenlabs_quota", return_value=_quota(37)):
            assert scheduler.generate_daily_videos() == 0

    def test_still_notifies_with_the_reason(self, scheduler):
        """The operator alert is the only channel that explains *why*."""
        with patch.object(credits, "elevenlabs_quota", return_value=_quota(37)):
            scheduler.generate_daily_videos()

        scheduler._notify_videos_ready.assert_called_once()
        kwargs = scheduler._notify_videos_ready.call_args.kwargs
        assert kwargs["quota"]["remaining"] == 37
        assert "quota" in kwargs["blocked"].lower()

    def test_reuses_the_preflight_lookup_for_the_notification(self, real_notifier):
        """One quota lookup per run, not two — the real notifier runs here so a
        second lookup inside it would be caught."""
        import daily_scheduler
        with patch.object(credits, "elevenlabs_quota", return_value=_quota(37)) as q, \
             patch.object(daily_scheduler.notify, "send_telegram", return_value=True):
            real_notifier.generate_daily_videos()

        assert q.call_count == 1

    def test_notification_message_carries_the_quota_and_the_reason(self, real_notifier):
        import daily_scheduler
        with patch.object(credits, "elevenlabs_quota", return_value=_quota(37)), \
             patch.object(daily_scheduler.notify, "send_telegram", return_value=True) as send:
            real_notifier.generate_daily_videos()

        message = send.call_args.args[0]
        assert "37 of 10,000" in message
        assert "0 long-form + 0 short-form = 0 videos" in message
        assert "quota exhausted" in message


class TestPreflightLeavesUsableBatchesAlone:
    def test_healthy_quota_runs_the_full_batch(self, scheduler):
        scheduler.rhyme_manager.popular_rhymes = [
            {"id": f"p{i}", "title": f"Rhyme {i}", "text": "la la"} for i in range(5)
        ]
        scheduler.rhyme_manager.generate_new_rhyme.return_value = {
            "id": "g1", "title": "Generated", "text": "la la",
        }
        scheduler.video_generator.generate_long_form_video.return_value = "/tmp/long.mp4"
        scheduler.video_generator.extract_shorts_from_long.return_value = [
            "/tmp/s1.mp4", "/tmp/s2.mp4",
        ]

        with patch.object(credits, "elevenlabs_quota", return_value=_quota(7_500)):
            produced = scheduler.generate_daily_videos()

        assert produced == 5
        assert scheduler.video_generator.generate_long_form_video.call_count == 5

    def test_unreadable_quota_does_not_block_the_batch(self, scheduler):
        scheduler.rhyme_manager.popular_rhymes = [
            {"id": "p0", "title": "Rhyme", "text": "la la"},
        ]
        scheduler.video_generator.generate_long_form_video.return_value = "/tmp/long.mp4"
        scheduler.video_generator.extract_shorts_from_long.return_value = ["/tmp/s1.mp4"]

        with patch.object(credits, "elevenlabs_quota", return_value=None):
            produced = scheduler.generate_daily_videos(count=1, force_source="popular")

        assert produced == 1
        scheduler.video_generator.generate_long_form_video.assert_called_once()
