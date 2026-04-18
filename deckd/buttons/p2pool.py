"""P2Pool systemd toggle key."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable

from deckd.buttons.base import DeckButton
from deckd.systemd_unit import (
    connect_system_bus,
    get_manager_interface,
    get_unit_active_state,
    get_unit_object_path,
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
        unit: str,
        images_dir: Any,
        *,
        loop: asyncio.AbstractEventLoop,
        refresh_deck: Callable[[DeckButton], None],
        bus_holder: list[Any],
    ) -> None:
        super().__init__(key_index)
        self._unit = unit
        self._images_dir = images_dir
        self._loop = loop
        self._refresh_deck = refresh_deck
        self._bus_holder = bus_holder
        self._active_state = "inactive"

    def set_active_state(self, state: str) -> None:
        lower = state.lower()
        if lower == self._active_state:
            return
        self._active_state = lower
        self._refresh_deck(self)

    def get_image_path(self) -> str:
        if self._active_state == "active":
            return str(self._images_dir / "monero_online.png")
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
            want_active = state.lower() != "active"
            await try_start_stop(bus, self._unit, want_active)

        fut = asyncio.run_coroutine_threadsafe(_toggle(), self._loop)

        def _log_exc(f: asyncio.Future[Any]) -> None:
            exc = f.exception()
            if exc is not None:
                logger.exception("P2Pool toggle failed", exc_info=exc)

        fut.add_done_callback(_log_exc)

    def on_release(self, deck: Any) -> None:
        return None
