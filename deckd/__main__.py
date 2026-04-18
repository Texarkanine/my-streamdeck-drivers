"""CLI entrypoint for deckd."""

from __future__ import annotations

import argparse
import asyncio
import logging
import threading
from pathlib import Path

from deckd.config import AppConfig, load_config
from deckd.deck_runtime import BlankButton, DeckRuntime, run_deck_forever
from deckd.http_server import create_onair_app, run_flask_in_thread
from deckd.netutil import guess_primary_ipv4
from deckd.onair_client import register_sign
from deckd.systemd_unit import (
    connect_system_bus,
    get_manager_interface,
    get_unit_active_state,
    get_unit_object_path,
    subscribe_active_state_changes,
)

logger = logging.getLogger(__name__)


class OnAirState:
    """Thread-safe holder for the last known on-air boolean."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value = False

    def get(self) -> bool:
        with self._lock:
            return self._value

    def set(self, value: bool) -> None:
        with self._lock:
            self._value = value


async def _async_main(cfg: AppConfig) -> None:
    loop = asyncio.get_running_loop()
    bus_holder: list = [None]

    deck_runtime = DeckRuntime()
    onair_state = OnAirState()

    from deckd.buttons.onair import OnAirButton
    from deckd.buttons.p2pool import P2PoolButton

    p2pool = P2PoolButton(
        0,
        cfg.p2pool.unit,
        cfg.images.dir,
        loop=loop,
        refresh_deck=deck_runtime.refresh,
        bus_holder=bus_holder,
    )
    onair = OnAirButton(1, cfg.images.dir, cfg.onair.server, onair_state.get)
    blanks = [BlankButton(k) for k in range(2, 6)]
    deck_runtime.set_buttons([p2pool, onair, *blanks])

    def apply_state(value: bool) -> None:
        onair_state.set(value)
        deck_runtime.refresh(onair)

    app = create_onair_app(onair_state.get, apply_state)
    run_flask_in_thread(app, "0.0.0.0", cfg.general.listen_port)

    bus = await connect_system_bus()
    bus_holder[0] = bus
    manager = await get_manager_interface(bus)
    unit_path = await get_unit_object_path(manager, cfg.p2pool.unit)
    active = await get_unit_active_state(bus, unit_path)
    p2pool.set_active_state(active)

    async def on_unit_active_change(new_state: str) -> None:
        p2pool.set_active_state(new_state)

    await subscribe_active_state_changes(bus, unit_path, on_unit_active_change)

    deck_thread = threading.Thread(target=run_deck_forever, args=(deck_runtime,), name="deckd-hid", daemon=True)
    deck_thread.start()

    async def register_loop() -> None:
        while True:
            try:
                callback_base = f"http://{guess_primary_ipv4()}:{cfg.general.listen_port}"
                register_sign(cfg.onair.server, callback_base)
            except Exception:
                logger.exception("OnAir register failed")
            if cfg.onair.register_interval <= 0:
                return
            await asyncio.sleep(cfg.onair.register_interval)

    await asyncio.gather(
        register_loop(),
        asyncio.Event().wait(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream Deck daemon (deckd)")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to deckd.toml",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = load_config(Path(args.config))
    try:
        asyncio.run(_async_main(cfg))
    except KeyboardInterrupt:
        logger.info("Interrupted")


if __name__ == "__main__":
    main()
