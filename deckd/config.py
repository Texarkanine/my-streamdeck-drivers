"""Load and validate deckd configuration (TOML)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import tomli


@dataclass(frozen=True)
class GeneralConfig:
    listen_port: int


@dataclass(frozen=True)
class P2PoolConfig:
    unit: str
    # Filenames under images.dir; alternated while unit ActiveState is "deactivating"
    deactivating_image_a: str
    deactivating_image_b: str
    # Seconds between frame flips (2 FPS ⇒ 0.5)
    deactivating_blink_interval_sec: float
    # SIG number for second press while stuck deactivating (9 = SIGKILL)
    deactivating_escalate_signal: int


@dataclass(frozen=True)
class OnAirConfig:
    server: str
    register_interval: float


@dataclass(frozen=True)
class ImagesConfig:
    dir: Path


@dataclass(frozen=True)
class AppConfig:
    general: GeneralConfig
    p2pool: P2PoolConfig
    onair: OnAirConfig
    images: ImagesConfig


def _require_section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if name not in data:
        raise ValueError(f"Missing [{name}] section in config")
    section = data[name]
    if not isinstance(section, Mapping):
        raise ValueError(f"[{name}] must be a table")
    return section


def _require_int(section: Mapping[str, Any], key: str) -> int:
    if key not in section:
        raise ValueError(f"Missing {key!r} in config section")
    value = section[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key!r} must be an integer")
    return value


def _require_float(section: Mapping[str, Any], key: str) -> float:
    if key not in section:
        raise ValueError(f"Missing {key!r} in config section")
    value = section[key]
    if isinstance(value, bool):
        raise ValueError(f"{key!r} must be a number")
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    raise ValueError(f"{key!r} must be a number")


def _require_str(section: Mapping[str, Any], key: str) -> str:
    if key not in section:
        raise ValueError(f"Missing {key!r} in config section")
    value = section[key]
    if not isinstance(value, str):
        raise ValueError(f"{key!r} must be a string")
    return value


def _optional_str(section: Mapping[str, Any], key: str, default: str) -> str:
    if key not in section:
        return default
    value = section[key]
    if not isinstance(value, str):
        raise ValueError(f"{key!r} must be a string")
    return value


def _optional_int(section: Mapping[str, Any], key: str, default: int) -> int:
    if key not in section:
        return default
    value = section[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key!r} must be an integer")
    return value


def _optional_float(section: Mapping[str, Any], key: str, default: float) -> float:
    if key not in section:
        return default
    value = section[key]
    if isinstance(value, bool):
        raise ValueError(f"{key!r} must be a number")
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    raise ValueError(f"{key!r} must be a number")


def load_config(path: Path) -> AppConfig:
    """Parse *path* as TOML and return a validated :class:`AppConfig`."""
    raw = path.read_bytes()
    data = tomli.loads(raw.decode("utf-8"))

    general = _require_section(data, "general")
    p2pool = _require_section(data, "p2pool")
    onair = _require_section(data, "onair")
    images = _require_section(data, "images")

    listen_port = _require_int(general, "listen_port")
    if listen_port < 1 or listen_port > 65535:
        raise ValueError("listen_port must be between 1 and 65535")

    unit = _require_str(p2pool, "unit")
    if not unit.endswith(".service"):
        raise ValueError('p2pool.unit must end with ".service"')
    deactivating_a = _optional_str(p2pool, "deactivating_image_a", "monero_deactivating_a.png")
    deactivating_b = _optional_str(p2pool, "deactivating_image_b", "monero_deactivating_b.png")
    blink_interval = _optional_float(p2pool, "deactivating_blink_interval_sec", 0.5)
    if blink_interval <= 0:
        raise ValueError("p2pool.deactivating_blink_interval_sec must be > 0")
    escalate_sig = _optional_int(p2pool, "deactivating_escalate_signal", 9)
    if escalate_sig < 1 or escalate_sig > 64:
        raise ValueError("p2pool.deactivating_escalate_signal must be between 1 and 64")

    server = _require_str(onair, "server").rstrip("/")
    register_interval = _require_float(onair, "register_interval")
    if register_interval < 0:
        raise ValueError("onair.register_interval must be >= 0")

    images_dir = Path(_require_str(images, "dir")).expanduser()

    return AppConfig(
        general=GeneralConfig(listen_port=listen_port),
        p2pool=P2PoolConfig(
            unit=unit,
            deactivating_image_a=deactivating_a,
            deactivating_image_b=deactivating_b,
            deactivating_blink_interval_sec=blink_interval,
            deactivating_escalate_signal=escalate_sig,
        ),
        onair=OnAirConfig(server=server, register_interval=register_interval),
        images=ImagesConfig(dir=images_dir),
    )
