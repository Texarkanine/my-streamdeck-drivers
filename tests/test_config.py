"""Tests for deckd.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from deckd.config import load_config


def test_load_valid_config(tmp_path: Path) -> None:
    path = tmp_path / "deckd.toml"
    path.write_text(
        """
[general]
listen_port = 5111

[p2pool]
unit = "p2pool.service"

[onair]
server = "http://localhost:1920"
register_interval = 60

[images]
dir = "/opt/deckd/images"
""".strip(),
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.general.listen_port == 5111
    assert cfg.p2pool.unit == "p2pool.service"
    assert cfg.p2pool.deactivating_image_a == "monero_deactivating_a.png"
    assert cfg.p2pool.deactivating_image_b == "monero_deactivating_b.png"
    assert cfg.p2pool.deactivating_blink_interval_sec == 0.5
    assert cfg.p2pool.deactivating_escalate_signal == 9
    assert cfg.onair.server == "http://localhost:1920"
    assert cfg.onair.register_interval == 60.0
    assert cfg.images.dir == Path("/opt/deckd/images")


def test_missing_section_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("[general]\nlisten_port = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="p2pool"):
        load_config(path)


def test_blink_interval_must_be_positive(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        """
[general]
listen_port = 1
[p2pool]
unit = "p2pool.service"
deactivating_blink_interval_sec = 0
[onair]
server = "http://x"
register_interval = 0
[images]
dir = "/x"
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="deactivating_blink_interval"):
        load_config(path)


def test_unit_must_end_with_service(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        """
[general]
listen_port = 1
[p2pool]
unit = "p2pool"
[onair]
server = "http://x"
register_interval = 0
[images]
dir = "/x"
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=".service"):
        load_config(path)
