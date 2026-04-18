"""OnAir toggle + sign key."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from deckd.buttons.base import DeckButton
from deckd.onair_client import put_state

logger = logging.getLogger(__name__)


class OnAirButton(DeckButton):
    """Key that shows on-air state and toggles via PUT."""

    def __init__(
        self,
        key_index: int,
        images_dir: Any,
        onair_server: str,
        get_state: Callable[[], bool],
        *,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__(key_index)
        self._images_dir = images_dir
        self._onair_server = onair_server.rstrip("/")
        self._get_state = get_state
        self._loop = loop

    def get_image_path(self) -> str:
        if self._get_state():
            return str(self._images_dir / "onair_on.png")
        return str(self._images_dir / "onair_off.png")

    def on_press(self, deck: Any) -> None:
        """Handle key down on the device thread."""
        current = self._get_state()
        new_state = not current

        async def _dispatch(state: bool) -> None:
            await asyncio.to_thread(put_state, self._onair_server, state)

        fut = asyncio.run_coroutine_threadsafe(_dispatch(new_state), self._loop)

        def _log_exc(f: Any) -> None:
            exc = f.exception()
            if exc is not None:
                logger.exception("OnAir toggle failed", exc_info=exc)

        fut.add_done_callback(_log_exc)

    def on_release(self, deck: Any) -> None:
        return None
