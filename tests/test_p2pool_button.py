"""Tests for P2Pool button image selection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from deckd.buttons.p2pool import P2PoolButton
from deckd.config import P2PoolConfig


def test_get_image_path_states() -> None:
    loop = asyncio.new_event_loop()
    cfg = P2PoolConfig(
        unit="p2pool.service",
        deactivating_image_a="a.png",
        deactivating_image_b="b.png",
        deactivating_blink_interval_sec=0.5,
    )
    btn = P2PoolButton(
        0,
        cfg,
        Path("/img"),
        loop=loop,
        refresh_deck=MagicMock(),
        bus_holder=[None],
    )
    btn._active_state = "active"
    assert btn.get_image_path() == "/img/monero_online.png"
    btn._active_state = "inactive"
    assert btn.get_image_path() == "/img/monero_offline.png"
    btn._active_state = "deactivating"
    btn._deactivating_frame = 0
    assert btn.get_image_path() == "/img/a.png"
    btn._deactivating_frame = 1
    assert btn.get_image_path() == "/img/b.png"
    loop.close()
