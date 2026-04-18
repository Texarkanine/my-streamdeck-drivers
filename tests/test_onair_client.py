"""Tests for OnAir HTTP client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from deckd.onair_client import register_sign


@patch("deckd.onair_client.requests.post")
def test_register_sends_json_string_body(mock_post: MagicMock) -> None:
    mock_post.return_value.content = b"{}"
    mock_post.return_value.json.return_value = {"ok": True}
    mock_post.return_value.raise_for_status = MagicMock()

    register_sign("http://127.0.0.1:1920", "http://10.0.0.5:5111")

    mock_post.assert_called_once()
    _args, kwargs = mock_post.call_args
    assert kwargs.get("json") == "http://10.0.0.5:5111/onair/api/v1/state"
