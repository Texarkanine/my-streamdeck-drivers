"""Stream Deck device wiring and thread-safe image updates."""

from __future__ import annotations

import logging
import threading
from typing import Any

from StreamDeck.DeviceManager import DeviceManager

from deckd.buttons.base import DeckButton

logger = logging.getLogger(__name__)


class BlankButton(DeckButton):
    """Dark key for reserved slots."""

    def __init__(self, key_index: int) -> None:
        super().__init__(key_index)

    def get_image_path(self) -> str:
        return ""

    def on_press(self, deck: Any) -> None:
        return None

    def on_release(self, deck: Any) -> None:
        return None

    def update_display(self, deck: Any) -> None:
        from PIL import Image
        from StreamDeck.ImageHelpers import PILHelper

        w, h = deck.KEY_PIXEL_WIDTH, deck.KEY_PIXEL_HEIGHT
        image = Image.new("RGB", (w, h), (0, 0, 0))
        native = PILHelper.to_native_format(deck, PILHelper.create_scaled_image(deck, image))
        deck.set_key_image(self.key_index, native)


class DeckRuntime:
    """Owns the HID device, routes key events, and serializes image updates."""

    def __init__(self) -> None:
        self._by_key: dict[int, DeckButton] = {}
        self._deck: Any | None = None
        self._lock = threading.Lock()

    def set_buttons(self, buttons: list[DeckButton]) -> None:
        self._by_key = {b.key_index: b for b in buttons}

    def attach(self, deck: Any) -> None:
        self._deck = deck

    def refresh(self, button: DeckButton) -> None:
        """Redraw *button* from the device thread or any asyncio/worker thread."""
        if self._deck is None:
            return
        with self._lock:
            button.update_display(self._deck)

    def key_callback(self, deck: Any, key: int, state: bool) -> None:
        button = self._by_key.get(key)
        if button is None:
            return
        if state:
            button.on_press(deck)
        else:
            button.on_release(deck)


def run_deck_forever(runtime: DeckRuntime) -> None:
    """Open the first device, paint keys, and keep the HID thread alive.

    ``StreamDeck.open()`` starts the internal reader thread; there is no
    separate ``run()`` call in current ``streamdeck`` releases.
    """
    decks = DeviceManager().enumerate()
    if not decks:
        raise RuntimeError("No Stream Deck found")
    deck = decks[0]
    runtime.attach(deck)
    deck.set_key_callback(runtime.key_callback)
    deck.open()
    deck.reset()
    logger.info("Stream Deck device opened: %s", deck.deck_type())
    for button in sorted(runtime._by_key.values(), key=lambda b: b.key_index):
        runtime.refresh(button)
    threading.Event().wait()
