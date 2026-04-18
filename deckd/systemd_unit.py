"""Async helpers for systemd over D-Bus (dbus-next)."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any, Callable, Coroutine, Literal

from dbus_next import BusType
from dbus_next.aio import MessageBus

logger = logging.getLogger(__name__)

P2PoolPressKind = Literal["stop", "start", "kill", "noop"]


def p2pool_press_kind(active_state: str) -> P2PoolPressKind:
    """Map systemd ``ActiveState`` to what the P2Pool key should do on press.

    * ``active`` → graceful stop (``StopUnit``).
    * ``deactivating`` → escalation (``KillUnit``, never start/restart).
    * ``inactive`` / ``failed`` → start.
    * ``activating`` and other values → no-op (avoids accidental start while coming up).
    """
    s = active_state.lower()
    if s == "active":
        return "stop"
    if s == "deactivating":
        return "kill"
    if s in ("inactive", "failed"):
        return "start"
    return "noop"


async def connect_system_bus() -> MessageBus:
    bus = MessageBus(bus_type=BusType.SYSTEM)
    return await bus.connect()


async def get_manager_interface(bus: MessageBus):
    intro = await bus.introspect("org.freedesktop.systemd1", "/org/freedesktop/systemd1")
    obj = bus.get_proxy_object(
        "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1",
        intro,
    )
    return obj.get_interface("org.freedesktop.systemd1.Manager")


async def get_unit_object_path(manager, unit_name: str) -> str:
    return await manager.call_get_unit(unit_name)


async def get_unit_active_state(bus: MessageBus, unit_path: str) -> str:
    intro = await bus.introspect("org.freedesktop.systemd1", unit_path)
    obj = bus.get_proxy_object("org.freedesktop.systemd1", unit_path, intro)
    iface = obj.get_interface("org.freedesktop.systemd1.Unit")
    return await iface.get_active_state()


async def start_unit(bus: MessageBus, unit_name: str) -> None:
    manager = await get_manager_interface(bus)
    await manager.call_start_unit(unit_name, "replace")


async def stop_unit(bus: MessageBus, unit_name: str) -> None:
    manager = await get_manager_interface(bus)
    await manager.call_stop_unit(unit_name, "replace")


async def kill_unit(bus: MessageBus, unit_name: str, signal: int) -> None:
    """Send *signal* to processes in the unit cgroup (systemd ``KillUnit``)."""
    manager = await get_manager_interface(bus)
    await manager.call_kill_unit(unit_name, "all", signal)


def systemctl_kill(unit: str, signal: int) -> None:
    subprocess.run(["systemctl", "kill", "-s", str(signal), unit], check=True)


async def try_kill_unit(bus: MessageBus | None, unit: str, signal: int) -> None:
    """``KillUnit`` over D-Bus, falling back to ``systemctl kill``."""
    if bus is not None:
        try:
            await kill_unit(bus, unit, signal)
            return
        except Exception:
            logger.exception("D-Bus KillUnit failed; trying systemctl kill fallback")
    systemctl_kill(unit, signal)


def systemctl_start(unit: str) -> None:
    subprocess.run(["systemctl", "start", unit], check=True)


def systemctl_stop(unit: str) -> None:
    subprocess.run(["systemctl", "stop", unit], check=True)


async def try_start_stop(bus: MessageBus | None, unit: str, want_active: bool) -> None:
    """Start or stop *unit* via D-Bus, falling back to ``systemctl`` on failure."""
    if bus is not None:
        try:
            if want_active:
                await start_unit(bus, unit)
            else:
                await stop_unit(bus, unit)
            return
        except Exception:
            logger.exception("D-Bus StartUnit/StopUnit failed; trying systemctl fallback")
    if want_active:
        systemctl_start(unit)
    else:
        systemctl_stop(unit)


def _variant_to_str(value: Any) -> str:
    if hasattr(value, "value"):
        inner = value.value
        return inner if isinstance(inner, str) else str(inner)
    return str(value)


async def subscribe_active_state_changes(
    bus: MessageBus,
    unit_path: str,
    on_change: Callable[[str], Coroutine[None, None, None]],
) -> None:
    """Subscribe to ``ActiveState`` changes for the unit at *unit_path*."""
    intro = await bus.introspect("org.freedesktop.systemd1", unit_path)
    obj = bus.get_proxy_object("org.freedesktop.systemd1", unit_path, intro)
    prop = obj.get_interface("org.freedesktop.DBus.Properties")

    def _handler(interface: str, changed: dict[str, Any], _invalidated: list[str]) -> None:
        if interface != "org.freedesktop.systemd1.Unit":
            return
        if "ActiveState" not in changed:
            return
        value = _variant_to_str(changed["ActiveState"])
        loop = asyncio.get_running_loop()
        loop.create_task(on_change(value))

    prop.on_properties_changed(_handler)  # type: ignore[attr-defined]
