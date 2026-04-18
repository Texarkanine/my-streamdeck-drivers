"""Tests for P2Pool press / ActiveState mapping."""

from __future__ import annotations

import pytest

from deckd.systemd_unit import p2pool_press_kind


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("active", "stop"),
        ("deactivating", "kill"),
        ("inactive", "start"),
        ("failed", "start"),
        ("activating", "noop"),
        ("reloading", "noop"),
    ],
)
def test_p2pool_press_kind(state: str, expected: str) -> None:
    assert p2pool_press_kind(state) == expected
