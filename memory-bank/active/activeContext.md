# Active Context

**Current Task:** Implement `deckd` per VISION + systemd deployment

**Phase:** BUILD — complete (QA pending)

**What Was Done:** Implemented `deckd` package (config, P2Pool D-Bus + fallback, OnAir HTTP sign + client, Stream Deck wiring, `__main__`), `install/` systemd + udev, `deckd.toml.example`, `images/README.md`, root `README.md`, `uv.lock`. Tests: `tests/test_config.py`, `tests/test_http_server.py`. Target server: Ubuntu 22.04 / Python 3.10 noted in `.python-version` and README.

**Next Step:** Operator runs `/niko-qa` or manual validation on kinglear; hardware/integration testing only on device.
