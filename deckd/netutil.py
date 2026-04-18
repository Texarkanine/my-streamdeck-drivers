"""Small network helpers for sign registration."""

from __future__ import annotations

import socket


def guess_primary_ipv4() -> str:
    """Return a best-effort LAN IPv4 address for callback URLs.

    Falls back to ``127.0.0.1`` if detection fails (e.g. offline).
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()
