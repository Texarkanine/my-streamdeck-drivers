# System Patterns

## How This System Works

The project is a **greenfield** Python daemon (`deckd`) built around the `streamdeck` library. A small **button** abstraction maps each physical key to image selection and press handling. **P2Pool** logic stays in systemd land: subscribe to D-Bus for unit state, and start/stop via D-Bus (with a documented fallback if authorization fails). **OnAir** logic mirrors existing “sign” behavior: register with the OnAir server, run a minimal embedded HTTP listener for `GET`/`PUT` `/onair/api/v1/state`, and periodically re-register so the server does not drop the sign after failed pushes.

Concurrency will need a clear story: the Stream Deck SDK uses callbacks (often off the main thread), OnAir may use Flask in a thread, and D-Bus may use asyncio—shared state should cross these boundaries via queues or explicit synchronization; that boundary is load-bearing once code exists.

## Planned layout

- Package-style layout under `deckd/` with `buttons/` for per-key behavior, `deck.py` for device wiring, `http_server.py` for the sign endpoint.
- Single config file (TOML or JSON) for listen port, unit name, OnAir base URL, image directory, and re-registration interval.
