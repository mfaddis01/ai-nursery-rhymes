#!/usr/bin/env python3
"""Tests for RhymeManager against the Claude Code CLI subprocess.

Replaces an earlier suite that patched `rhyme_manager.requests`. That suite
targeted a local HTTP server which no longer exists — generation was refactored
to a one-shot `claude -p` subprocess — so every one of its tests failed with
`AttributeError: module 'rhyme_manager' has no attribute 'requests'`.

The failure paths it covered still matter, so they carry over here against the
mechanism actually in use: a dead server becomes a non-zero exit, a timeout
stays a timeout, and unparseable output stays unparseable. The load-bearing
property throughout is that a failed generation must not persist a partial
rhyme, because the 06:00 batch runs unattended.

This suite is also the green baseline the autonomy layer gates on: an autonomous
run refuses to start unless these pass, and reverts itself if it breaks them.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rhyme_manager import RhymeManager  # noqa: E402


@pytest.fixture
def manager(tmp_path: Path) -> RhymeManager:
    """A manager rooted in a temp dir so tests never touch real ./data."""
    return RhymeManager(data_dir=str(tmp_path))


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


VALID = json.dumps({"title": "Sleepy Moon", "text": "line one\nline two"})


# --- _parse_rhyme_json --------------------------------------------------------

class TestParseRhymeJson:
    def test_parses_bare_json(self):
        assert RhymeManager._parse_rhyme_json(VALID) == {
            "title": "Sleepy Moon",
            "text": "line one\nline two",
        }

    def test_parses_fenced_json(self):
        """The prompt forbids a code fence; models add one anyway."""
        assert RhymeManager._parse_rhyme_json(f"```json\n{VALID}\n```")["title"] == "Sleepy Moon"

    def test_parses_json_embedded_in_prose(self):
        out = RhymeManager._parse_rhyme_json(f"Here you go!\n{VALID}\nHope that helps.")
        assert out["title"] == "Sleepy Moon"

    def test_rejects_output_with_no_json(self):
        with pytest.raises(ValueError, match="no JSON object"):
            RhymeManager._parse_rhyme_json("I'd be happy to help with that.")

    @pytest.mark.parametrize("payload", [
        {"title": "", "text": "some text"},
        {"title": "Only A Title", "text": ""},
        {"text": "missing title entirely"},
        {"title": "missing text entirely"},
    ])
    def test_rejects_missing_title_or_text(self, payload):
        with pytest.raises(ValueError, match="missing title or text"):
            RhymeManager._parse_rhyme_json(json.dumps(payload))


# --- _call_claude -------------------------------------------------------------

class TestCallClaude:
    def test_returns_stripped_stdout(self, manager):
        with patch("subprocess.run", return_value=_completed(stdout=f"  {VALID}  ")):
            assert manager._call_claude("prompt") == VALID

    def test_non_zero_exit_raises_with_the_code(self, manager):
        """Successor to the old 'server unreachable' case."""
        with patch("subprocess.run", return_value=_completed(returncode=1, stderr="boom")):
            with pytest.raises(RuntimeError, match="exited 1"):
                manager._call_claude("prompt")

    def test_empty_output_raises(self, manager):
        with patch("subprocess.run", return_value=_completed(stdout="   ")):
            with pytest.raises(RuntimeError, match="empty output"):
                manager._call_claude("prompt")

    def test_timeout_propagates(self, manager):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)):
            with pytest.raises(subprocess.TimeoutExpired):
                manager._call_claude("prompt")

    def test_strips_anthropic_credentials_from_subprocess_env(self, manager):
        """An inherited API key makes the CLI exit 1; generation uses its own login."""
        with patch("subprocess.run", return_value=_completed(stdout=VALID)) as run, \
             patch.dict("os.environ",
                        {"ANTHROPIC_API_KEY": "sk-test", "ANTHROPIC_AUTH_TOKEN": "tok"},
                        clear=False):
            manager._call_claude("prompt")
        env = run.call_args[1]["env"]
        assert "ANTHROPIC_API_KEY" not in env
        assert "ANTHROPIC_AUTH_TOKEN" not in env


# --- generate_new_rhyme -------------------------------------------------------

class TestGenerateNewRhyme:
    def test_returns_and_persists_on_success(self, manager):
        with patch.object(manager, "_call_claude", return_value=VALID):
            rhyme = manager.generate_new_rhyme(theme="moon")
        assert rhyme["title"] == "Sleepy Moon"
        assert rhyme["source"] == "ai-generated"
        assert any(r["title"] == "Sleepy Moon" for r in manager.generated_rhymes)

    @pytest.mark.parametrize("failure", [
        RuntimeError("claude CLI exited 1: boom"),
        RuntimeError("claude CLI returned empty output"),
        ValueError("no JSON object in claude output: ..."),
        subprocess.TimeoutExpired("claude", 300),
    ])
    def test_failed_generation_persists_nothing(self, manager, failure):
        """The one that matters: a partial rhyme must never reach the store."""
        before = len(manager.generated_rhymes)
        with patch.object(manager, "_call_claude", side_effect=failure):
            with pytest.raises(type(failure)):
                manager.generate_new_rhyme(theme="moon")
        assert len(manager.generated_rhymes) == before

    def test_tells_claude_which_titles_already_exist(self, manager):
        """A fixed prompt returns the same rhyme forever, so prior titles are sent."""
        manager.generated_rhymes.append({"title": "Sleepy Moon", "text": "x"})
        with patch.object(manager, "_call_claude", return_value=VALID) as call:
            manager.generate_new_rhyme(theme="stars")
        assert "Sleepy Moon" in call.call_args[0][0]


# --- retrieval ----------------------------------------------------------------

class TestRetrieval:
    def test_get_random_rhyme_raises_when_source_empty(self, manager):
        with pytest.raises(ValueError, match="No rhymes available"):
            manager.get_random_rhyme(source="ai-generated")

    def test_get_rhyme_by_id_returns_none_when_absent(self, manager):
        assert manager.get_rhyme_by_id("nope") is None

    def test_get_rhymes_by_theme_filters(self, manager):
        with patch.object(manager, "_call_claude", return_value=VALID):
            manager.generate_new_rhyme(theme="moon")
        assert len(manager.get_rhymes_by_theme("moon")) == 1
        assert manager.get_rhymes_by_theme("dinosaurs") == []
