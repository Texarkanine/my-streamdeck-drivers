"""HTTP client for OnAir registration and state PUT."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


def register_sign(onair_server_base: str, callback_base: str) -> Any:
    """Register this host as an OnAir sign.

    *onair_server_base* is e.g. ``http://host:1920``.
    *callback_base* is e.g. ``http://thishost:5111`` (no trailing slash).
    """
    url = f"{onair_server_base.rstrip('/')}/onair/api/v1/register"
    callback = f"{callback_base.rstrip('/')}/onair/api/v1/state"
    try:
        response = requests.post(
            url,
            data=callback.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=10,
        )
        response.raise_for_status()
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None
    except Exception:
        logger.exception("OnAir register failed for %s", url)
        raise


def put_state(onair_server_base: str, value: bool) -> None:
    """PUT global on-air state (matches watcher/sign clients)."""
    url = f"{onair_server_base.rstrip('/')}/onair/api/v1/state"
    try:
        response = requests.put(
            url,
            json=value,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("OnAir PUT failed for %s", url)
        raise
