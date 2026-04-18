"""Tests for deckd.systemd_unit async fallbacks and D-Bus subscription helper."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from deckd import systemd_unit


async def test_systemctl_kill_is_coroutine_and_invokes_subprocess_run() -> None:
    assert inspect.iscoroutinefunction(systemd_unit.systemctl_kill)

    with patch("deckd.systemd_unit.subprocess.run") as mock_run:
        coro = systemd_unit.systemctl_kill("p2pool.service", 9)
        assert inspect.iscoroutine(coro)
        await coro

    mock_run.assert_called_once_with(
        ["systemctl", "kill", "-s", "9", "p2pool.service"], check=True
    )


async def test_systemctl_start_is_coroutine_and_invokes_subprocess_run() -> None:
    assert inspect.iscoroutinefunction(systemd_unit.systemctl_start)

    with patch("deckd.systemd_unit.subprocess.run") as mock_run:
        await systemd_unit.systemctl_start("p2pool.service")

    mock_run.assert_called_once_with(
        ["systemctl", "start", "p2pool.service"], check=True
    )


async def test_systemctl_stop_is_coroutine_and_invokes_subprocess_run() -> None:
    assert inspect.iscoroutinefunction(systemd_unit.systemctl_stop)

    with patch("deckd.systemd_unit.subprocess.run") as mock_run:
        await systemd_unit.systemctl_stop("p2pool.service")

    mock_run.assert_called_once_with(
        ["systemctl", "stop", "p2pool.service"], check=True
    )


async def test_try_start_stop_awaits_systemctl_start_when_bus_is_none() -> None:
    async def fake_start(unit: str) -> None:
        fake_start.called_with = unit  # type: ignore[attr-defined]

    fake_start.called_with = None  # type: ignore[attr-defined]

    with patch.object(systemd_unit, "systemctl_start", fake_start):
        await systemd_unit.try_start_stop(None, "p2pool.service", want_active=True)

    assert fake_start.called_with == "p2pool.service"  # type: ignore[attr-defined]


async def test_try_start_stop_awaits_systemctl_stop_when_bus_is_none() -> None:
    async def fake_stop(unit: str) -> None:
        fake_stop.called_with = unit  # type: ignore[attr-defined]

    fake_stop.called_with = None  # type: ignore[attr-defined]

    with patch.object(systemd_unit, "systemctl_stop", fake_stop):
        await systemd_unit.try_start_stop(None, "p2pool.service", want_active=False)

    assert fake_stop.called_with == "p2pool.service"  # type: ignore[attr-defined]


async def test_try_kill_unit_awaits_systemctl_kill_when_bus_is_none() -> None:
    async def fake_kill(unit: str, signal: int) -> None:
        fake_kill.called_with = (unit, signal)  # type: ignore[attr-defined]

    fake_kill.called_with = None  # type: ignore[attr-defined]

    with patch.object(systemd_unit, "systemctl_kill", fake_kill):
        await systemd_unit.try_kill_unit(None, "p2pool.service", 15)

    assert fake_kill.called_with == ("p2pool.service", 15)  # type: ignore[attr-defined]


async def test_subscribe_on_change_exception_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If the on_change coroutine raises, the task's exception surfaces via logger.exception."""

    captured_handler: dict[str, Any] = {}

    class FakeProp:
        def on_properties_changed(self, handler: Any) -> None:
            captured_handler["handler"] = handler

    class FakeObj:
        def get_interface(self, name: str) -> FakeProp:
            return FakeProp()

    class FakeBus:
        async def introspect(self, *args: Any, **kwargs: Any) -> object:
            return object()

        def get_proxy_object(self, *args: Any, **kwargs: Any) -> FakeObj:
            return FakeObj()

    async def raising_handler(value: str) -> None:
        raise RuntimeError("boom")

    bus = FakeBus()
    await systemd_unit.subscribe_active_state_changes(
        bus,  # type: ignore[arg-type]
        "/org/freedesktop/systemd1/unit/p2pool_2eservice",
        raising_handler,
    )

    handler = captured_handler["handler"]

    class _V:
        def __init__(self, v: str) -> None:
            self.value = v

    with caplog.at_level(logging.ERROR, logger="deckd.systemd_unit"):
        handler("org.freedesktop.systemd1.Unit", {"ActiveState": _V("active")}, [])
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    matching = [
        r
        for r in caplog.records
        if r.name == "deckd.systemd_unit"
        and r.levelno >= logging.ERROR
        and "boom" in (r.message + (str(r.exc_info) if r.exc_info else ""))
    ]
    assert matching, (
        "Expected an error-level log from deckd.systemd_unit mentioning 'boom'; "
        f"got records: {[(r.name, r.levelname, r.message) for r in caplog.records]}"
    )
