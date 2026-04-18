"""Tests for the embedded OnAir HTTP listener."""

from __future__ import annotations

from deckd.http_server import create_onair_app


def test_get_put_roundtrip() -> None:
    state = {"value": False}

    def get_state() -> bool:
        return state["value"]

    def apply_state(v: bool) -> None:
        state["value"] = v

    app = create_onair_app(get_state, apply_state)
    client = app.test_client()

    get = client.get("/onair/api/v1/state")
    assert get.status_code == 200
    assert get.get_json() is False

    put = client.put("/onair/api/v1/state", json=True)
    assert put.status_code == 200
    assert put.get_json() is True

    get2 = client.get("/onair/api/v1/state")
    assert get2.get_json() is True


def test_put_rejects_non_boolean() -> None:
    app = create_onair_app(lambda: False, lambda v: None)
    client = app.test_client()
    resp = client.put("/onair/api/v1/state", json="nope")
    assert resp.status_code == 400
