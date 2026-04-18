# System Patterns

## How This System Works

`deckd` is a Python daemon around the `streamdeck` library. A small
**button** abstraction (`deckd/buttons/base.py`) maps each physical key
to image selection + press handling; concrete buttons live alongside
(`buttons/p2pool.py`, `buttons/onair.py`). **P2Pool** logic stays in
systemd land: subscribe to D-Bus for unit state and start/stop via D-Bus,
with a documented polkit-based authorization path and a `systemctl`
subprocess fallback. **OnAir** logic mirrors existing "sign" behavior:
register with the OnAir server, run a minimal embedded Flask listener
for `GET`/`PUT` `/onair/api/v1/state`, and periodically re-register.

**Concurrency model (load-bearing).** The process has one asyncio event
loop on the main thread and two daemon threads:

- **asyncio main loop**: D-Bus subscriber, OnAir periodic re-register.
- **Flask daemon thread**: the sign HTTP listener.
- **StreamDeck `run()` daemon thread**: USB key-press callbacks.

Any cross-thread work that must touch async state (e.g. a keypress that
needs to call D-Bus) is forwarded to the main loop via
`asyncio.run_coroutine_threadsafe`. This "one obvious main loop, two
dumb threads" shape is the mental model — deviating from it (e.g.
calling D-Bus directly from the StreamDeck thread) will break things.

Every blocking I/O call is bounced off its caller: synchronous HTTP
(`requests` in `register_sign` / `put_state`) and `subprocess.run`
(`systemctl_{kill,start,stop}`) are wrapped in `asyncio.to_thread(...)`
when called from the asyncio loop, and button press handlers that
originate on the HID callback thread forward to the loop via
`asyncio.run_coroutine_threadsafe` before doing any async work. This
keeps the event loop responsive to D-Bus `PropertiesChanged` signals and
keeps one stalled HTTP/`systemctl` call from blocking subsequent
keypresses.

Package layout lives under `deckd/`: `buttons/` for per-key behavior,
`deck_runtime.py` for device wiring, `http_server.py` for the sign
endpoint, `systemd_unit.py` for D-Bus + fallback, `onair_client.py` for
register/PUT, `config.py` for TOML loading, `__main__.py` for wiring.

Config is a single TOML file. Images are user-supplied PNGs in a
configurable directory (not checked into the repo).

## Systemd unit state as a six-value machine, not a boolean

`ActiveState` has `active`, `inactive`, `activating`, `deactivating`,
`failed`, `reloading` — not just two. Units can stall in `deactivating`
for minutes. The P2Pool button handles this with a two-frame blink
animation (`deactivating_image_a`/`_b` at a configurable interval) and
an optional repeat-press escalation that calls systemd `KillUnit` with
a configured signal (e.g. 15 = SIGTERM, 9 = SIGKILL). `StartUnit` is
**never** invoked while the unit is `deactivating`. Evidence:
`deckd/buttons/p2pool.py`, `deckd/systemd_unit.py`. Any future
service-toggle button should assume the same state-machine shape.

## `Manager.Subscribe()` is required for spec-correct PropertiesChanged delivery

systemd's D-Bus contract says clients must call
`org.freedesktop.systemd1.Manager.Subscribe` once per connection
before they can rely on `PropertiesChanged` signals for units.
`dbus-next`'s `call_properties_changed` subscription can appear to
"just work" without it (systemd emits signals incidentally on unit
interaction), which is how deckd's first revision got away without
it. deckd now calls `manager.call_subscribe()` once at startup in
`deckd/__main__.py` (wrapped in `try/except` — a failure here is
logged and tolerated since the incidental path remains). Any future
feature that subscribes to systemd unit properties should assume
`Subscribe` has been called.

## Polkit authorization is user-scoped, not unit-scoped

`action.lookup("unit")` in polkit rules does not return a matchable
string across all systemd versions, so unit-specific rules silently
fail auth. The install artifacts (`install/polkit/99-deckd-p2pool.rules`
and the `.pkla` fallback) allow `org.freedesktop.systemd1.manage-units`
for a specific Unix user; narrowing is best done via a dedicated
service account or group membership. Do not attempt to re-introduce
unit-name filtering in polkit rules.
