"""Abstract button and shared image update helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DeckButton(ABC):
    """One logical key: maps state to PNG paths and handles press/release."""

    key_index: int

    def __init__(self, key_index: int) -> None:
        self.key_index = key_index

    @abstractmethod
    def get_image_path(self) -> str:
        """Return path to the PNG to show for the current state."""

    @abstractmethod
    def on_press(self, deck: Any) -> None:
        """Handle key down (device thread)."""

    @abstractmethod
    def on_release(self, deck: Any) -> None:
        """Handle key up (device thread)."""

    def update_display(self, deck: Any) -> None:
        """Load current PNG and push pixels to the device (caller holds deck lock)."""
        from PIL import Image
        from StreamDeck.ImageHelpers import PILHelper

        path = self.get_image_path()
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            scaled = PILHelper.create_scaled_image(deck, rgba)
            native = PILHelper.to_native_format(deck, scaled)
        deck.set_key_image(self.key_index, native)
