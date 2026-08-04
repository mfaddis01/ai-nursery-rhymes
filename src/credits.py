"""Remaining third-party quota for the video pipeline.

ElevenLabs TTS is the metered dependency: the free tier allows 10,000 characters
a month and a single rhyme costs several hundred, so an exhausted quota stops
video generation entirely while everything else still looks healthy. Pexels is
rate-limited rather than credit-metered, so it is reported separately when the
header is available.

Nothing here may break the pipeline. Every lookup returns None on any failure
rather than raising -- a credits display is worth less than a batch run.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 15
# A rhyme plus its title runs a few hundred characters; below this, the next
# generation almost certainly fails partway rather than cleanly.
LOW_CHARACTER_THRESHOLD = 1000


def elevenlabs_quota() -> Optional[dict]:
    """Character quota for the ElevenLabs key, or None if it cannot be read."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        logger.debug("credits: no ELEVENLABS_API_KEY set")
        return None
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": api_key},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        used = int(data["character_count"])
        limit = int(data["character_limit"])
    except Exception as e:  # network, auth, schema drift — all non-fatal
        logger.warning(f"credits: ElevenLabs quota unavailable: {e}")
        return None

    remaining = max(limit - used, 0)
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "pct_remaining": (remaining / limit * 100) if limit else 0.0,
        "tier": data.get("tier"),
        "resets_unix": data.get("next_character_count_reset_unix"),
        "low": remaining < LOW_CHARACTER_THRESHOLD,
    }


def format_credits_line(quota: Optional[dict]) -> str:
    """One-line human summary for the daily notification."""
    if quota is None:
        return "🎙️ ElevenLabs: quota unavailable (check ELEVENLABS_API_KEY)"

    from datetime import datetime

    resets = ""
    if quota.get("resets_unix"):
        try:
            resets = " · resets " + datetime.fromtimestamp(
                int(quota["resets_unix"])
            ).strftime("%b %d")
        except Exception:
            resets = ""

    marker = "⚠️ " if quota["low"] else ""
    line = (
        f"{marker}🎙️ ElevenLabs: {quota['remaining']:,} of {quota['limit']:,} "
        f"characters left ({quota['pct_remaining']:.0f}%)"
        f"{' · ' + quota['tier'] if quota.get('tier') else ''}{resets}"
    )
    if quota["low"]:
        line += "\n   Not enough for another rhyme — TTS will fail until this resets or the plan is upgraded."
    return line
