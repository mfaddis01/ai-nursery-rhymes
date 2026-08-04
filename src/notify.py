"""Telegram delivery for pipeline notifications.

The daily run has always written notifications/ready_*.json and then done
nothing with it, so a completed -- or empty -- batch was only visible by reading
files on the host. This sends it.

Uses this project's own bot (TELEGRAM_BOT_TOKEN in config.env), never the
trading bot's. Delivery never raises: a failed notification must not fail a
batch that otherwise succeeded.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 15


def send_telegram(text: str) -> bool:
    """Send a message. Returns True on delivery, False on any failure."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.info("notify: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set; skipping")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=_TIMEOUT,
        )
        payload = resp.json()
    except Exception as e:
        logger.warning(f"notify: telegram send failed: {e}")
        return False

    if not payload.get("ok"):
        # Log the API's reason, never the token. A configured-but-dead token
        # otherwise looks wired up while every message silently vanishes.
        logger.warning(f"notify: telegram rejected: {payload.get('description')}")
        return False
    return True
