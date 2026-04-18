"""Tests for OnAirButton.on_press async dispatch behavior."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from deckd.buttons.onair import OnAirButton


def _run_loop_in_thread(loop: asyncio.AbstractEventLoop) -> threading.Thread:
    t = threading.Thread(target=loop.run_forever, name="test-loop", daemon=True)
    t.start()
    return t


def _stop_loop_cleanly(loop: asyncio.AbstractEventLoop, thread: threading.Thread) -> None:
    """Drain pending tasks, then stop the loop and join its thread."""

    async def _drain() -> None:
        pending = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    try:
        asyncio.run_coroutine_threadsafe(_drain(), loop).result(timeout=3.0)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2.0)
        loop.close()


def test_on_press_returns_promptly_when_put_state_is_slow(monkeypatch) -> None:
    """on_press must return on the caller thread without blocking on put_state."""

    loop = asyncio.new_event_loop()
    loop_thread = _run_loop_in_thread(loop)
    try:
        call_happened = threading.Event()
        call_finished = threading.Event()

        def slow_put_state(server: str, state: bool) -> None:
            call_happened.set()
            time.sleep(0.3)
            call_finished.set()

        monkeypatch.setattr("deckd.buttons.onair.put_state", slow_put_state)

        btn = OnAirButton(
            1,
            Path("/img"),
            "http://onair.local",
            get_state=lambda: False,
            loop=loop,
        )

        t0 = time.monotonic()
        btn.on_press(deck=MagicMock())
        elapsed = time.monotonic() - t0

        assert elapsed < 0.05, f"on_press took {elapsed:.3f}s; expected <0.05s"
        assert call_happened.wait(timeout=1.0), "put_state was never invoked"
        assert call_finished.wait(timeout=2.0), "put_state never completed"
    finally:
        _stop_loop_cleanly(loop, loop_thread)


def test_on_press_dispatches_put_with_flipped_state(monkeypatch) -> None:
    """The scheduled coroutine eventually calls put_state with !current."""

    loop = asyncio.new_event_loop()
    loop_thread = _run_loop_in_thread(loop)
    try:
        captured: dict[str, object] = {}
        called = threading.Event()

        def capturing_put_state(server: str, state: bool) -> None:
            captured["server"] = server
            captured["state"] = state
            called.set()

        monkeypatch.setattr("deckd.buttons.onair.put_state", capturing_put_state)

        btn = OnAirButton(
            1,
            Path("/img"),
            "http://onair.local/",
            get_state=lambda: False,
            loop=loop,
        )

        btn.on_press(deck=MagicMock())
        assert called.wait(timeout=1.0), "put_state was never invoked"
        assert captured["server"] == "http://onair.local"
        assert captured["state"] is True
    finally:
        _stop_loop_cleanly(loop, loop_thread)
