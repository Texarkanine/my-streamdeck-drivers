"""P2Pool systemd toggle key."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable

from deckd.buttons.base import DeckButton
from deckd.config import P2PoolConfig
from deckd.systemd_unit import (
    connect_system_bus,
    get_manager_interface,
    get_unit_active_state,
    get_unit_object_path,
    p2pool_press_kind,
    try_kill_unit,
    try_start_stop,
)

if TYPE_CHECKING:
    from dbus_next.aio import MessageBus

logger = logging.getLogger(__name__)


class P2PoolButton(DeckButton):
    """Key that shows P2Pool unit state and toggles start/stop via D-Bus (with fallback)."""

    def __init__(
        self,
        key_index: int,
        p2pool: P2PoolConfig,
        images_dir: Any,
        *,
        loop: asyncio.AbstractEventLoop,
        refresh_deck: Callable[[DeckButton], None],
        bus_holder: list[Any],
    ) -> None:
        super().__init__(key_index)
        self._unit = p2pool.unit
        self._images_dir = images_dir
        self._deactivating_a = p2pool.deactivating_image_a
        self._deactivating_b = p2pool.deactivating_image_b
        self._blink_interval_sec = p2pool.deactivating_blink_interval_sec
        self._escalate_signal = p2pool.deactivating_escalate_signal
        self._loop = loop
        self._refresh_deck = refresh_deck
        self._bus_holder = bus_holder
        self._active_state = "inactive"
        self._deactivating_frame = 0
        self._blink_task: asyncio.Task[None] | None = None

    def _cancel_blink(self) -> None:
        if self._blink_task is None or self._blink_task.done():
            self._blink_task = None
            return
        self._blink_task.cancel()
        self._blink_task = None

    async def _blink_loop(self) -> None:
        try:
            while self._active_state == "deactivating":
                await asyncio.sleep(self._blink_interval_sec)
                if self._active_state != "deactivating":
                    return
                self._deactivating_frame = 1 - self._deactivating_frame
                self._refresh_deck(self)
        except asyncio.CancelledError:
            return

    def _start_blink(self) -> None:
        self._cancel_blink()
        self._blink_task = self._loop.create_task(self._blink_loop())

    def set_active_state(self, state: str) -> None:
        lower = state.lower()
        if lower == self._active_state:
            return
        self._cancel_blink()
        self._active_state = lower
        self._deactivating_frame = 0
        self._refresh_deck(self)
        if lower == "deactivating":
            self._start_blink()

    def get_image_path(self) -> str:
        if self._active_state == "active":
            return str(self._images_dir / "monero_online.png")
        if self._active_state == "deactivating":
            name = self._deactivating_a if self._deactivating_frame == 0 else self._deactivating_b
            return str(self._images_dir / name)
        return str(self._images_dir / "monero_offline.png")

    def on_press(self, deck: Any) -> None:
        """Handle key down on the device thread."""

        async def _toggle() -> None:
            bus: MessageBus | None = self._bus_holder[0]
            if bus is None:
                bus = await connect_system_bus()
                self._bus_holder[0] = bus
            manager = await get_manager_interface(bus)
            unit_path = await get_unit_object_path(manager, self._unit)
            state = await get_unit_active_state(bus, unit_path)
            kind = p2pool_press_kind(state)
            if kind == "stop":
                await try_start_stop(bus, self._unit, want_active=False)
            elif kind == "start":
                await try_start_stop(bus, self._unit, want_active=True)
            elif kind == "kill":
                await try_kill_unit(bus, self._unit, self._escalate_signal)
            else:
                logger.info("P2Pool: ignoring key press while unit ActiveState is %s", state)

        fut = asyncio.run_coroutine_threadsafe(_toggle(), self._loop)

        def _log_exc(f: asyncio.Future[Any]) -> None:
            exc = f.exception()
            if exc is not None:
                logger.exception("P2Pool toggle failed", exc_info=exc)

        fut.add_done_callback(_log_exc)

    def on_release(self, deck: Any) -> None:
        return None
