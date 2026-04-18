# `deckd` — Stream Deck Daemon for Headless Linux

## Summary

A headless Python daemon that drives an Elgato Stream Deck Mini (6-key) over USB, providing physical toggle buttons for local services. Runs as a systemd unit on a headless Linux server. No display server, no GUI, no Node.js, no auto-updates.

Two buttons at launch. Room for four more later.

## Hardware

- **Elgato Stream Deck Mini** (6 LCD keys, USB-C)
- **Host:** headless Linux server (the P2Pool / mining box)

## Dependencies

- Python 3.11+
- [`streamdeck`](https://github.com/abcminiuser/python-elgato-streamdeck) (MIT) — raw HID interface to Stream Deck hardware (pulls in Pillow transitively for image format conversion)
- `requests` — HTTP calls to OnAir server
- `dbus-next` (or `pydbus`) — subscribe to systemd unit state changes over D-Bus (avoids polling)
- Build toolchain: [`uv`](https://docs.astral.sh/uv/) with `pyproject.toml` + `uv.lock`

## Architecture

```
┌─────────────────────────────────────────────┐
│                   deckd                      │
│                                              │
│  ┌─────────────┐       ┌─────────────────┐  │
│  │ Button 0    │       │ Button 1        │  │
│  │ P2Pool      │       │ OnAir           │  │
│  │ Toggle      │       │ Toggle/Sign     │  │
│  └──────┬──────┘       └──────┬──────────┘  │
│         │                     │              │
│         ▼                     ▼              │
│  systemd D-Bus          OnAir Server API    │
│  (subscribe to          (register as sign,  │
│   unit state)            GET/PUT state)     │
└─────────────────────────────────────────────┘
```

### Event-driven, not polled

- **P2Pool status:** Subscribe to `org.freedesktop.systemd1` D-Bus signals for the `p2pool.service` unit. When the unit's `ActiveState` changes, update the button image immediately. No polling loop.
- **OnAir status:** Register with the OnAir server as a **sign** (POST to `/onair/api/v1/register`). The server pushes state changes to deckd's embedded HTTP listener, exactly like the existing Raspberry Pi signs do. The daemon already has Flask in-process for this (see OnAir sign architecture). Fallback: periodic re-registration (the existing sign code already does this at a configurable interval).

## Button Specifications

### Button 0 — P2Pool Toggle

#### Display

| State | Image |
|---|---|
| `p2pool.service` is `active` | `monero_online.png` |
| `p2pool.service` is `inactive`/`failed`/other | `monero_offline.png` |

#### Behavior on press

1. Query current `ActiveState` of `p2pool.service` via D-Bus (authoritative, not cached image state).
2. If `active` → `systemctl stop p2pool` (via D-Bus `StopUnit`).
3. If `inactive`/`failed` → `systemctl start p2pool` (via D-Bus `StartUnit`).
4. D-Bus subscription fires when the unit actually changes state → update image to new steady state.

#### Permissions

The daemon's user must be in a group (or have a polkit rule) that allows `org.freedesktop.systemd1.manage-units` for `p2pool.service`. Alternatively, run as root (not preferred) or add a sudoers NOPASSWD entry for the specific `systemctl` commands and shell out as a fallback if D-Bus auth is rejected.

### Button 1 — OnAir Toggle + Sign

This button serves a dual role: it is both a **control surface** (toggle on/off) and a **sign** (receives push updates from the OnAir server). This mirrors the existing `onair` system architecture where signs register with the server and receive state pushes.

#### Display

| State | Image |
|---|---|
| On-air | `onair_on.png` |
| Off-air | `onair_off.png` |

#### Behavior as a Sign (passive, receiving state)

On startup and periodically thereafter, deckd registers itself with the OnAir server as a sign, exactly as `sign/src/sign.py` does:

```
POST http://<onair-server>:1920/onair/api/v1/register
Body: "http://<deckd-host>:<deckd-port>/onair/api/v1/state"
```

The server responds with current state (boolean) and will subsequently push `PUT` updates to deckd's `/onair/api/v1/state` endpoint whenever any client changes the on-air state. On receiving a push, deckd updates button 1's image.

This means: if someone goes on-air from their laptop (via the existing watcher client), button 1 on the Stream Deck updates automatically. No polling.

#### Behavior on press (active, setting state)

1. Read current on-air state from local cache (last received push, or last GET).
2. Compute opposite: `new_state = not current_state`.
3. `PUT http://<onair-server>:1920/onair/api/v1/state` with body `true` or `false`.
4. The server processes this, then pushes the new state back to all registered signs — including deckd itself — which updates the button image.

No shelling out to `onair` script. The HTTP call is the same thing the script does:

```python
requests.put(
    f"http://{ONAIR_HOST}:{ONAIR_PORT}/onair/api/v1/state",
    json=new_state,
    headers={"Content-Type": "application/json"},
    timeout=10
)
```

#### OnAir HTTP listener

deckd runs a lightweight HTTP server (Flask or just `http.server`) to receive sign pushes from the OnAir server. This listener must:

- Accept `GET /onair/api/v1/state` → return current state as JSON boolean
- Accept `PUT /onair/api/v1/state` → update local state, update button image, return new state as JSON boolean

This is the same contract as `sign/src/sign.py`. It can likely share code or at minimum share the route definitions.

#### Re-registration

The OnAir server drops signs after `MAX_FAILURES` (currently 3) consecutive push failures. deckd must re-register periodically to stay in the sign list, especially across server restarts. The existing sign code uses a configurable interval (default 60s) via a background thread. Replicate this.

## Configuration

Single config file, e.g. `deckd.toml` or `deckd.json`:

```toml
[general]
# Port for the embedded HTTP listener (OnAir sign registration callback)
listen_port = 5111

[p2pool]
# systemd unit name to monitor/toggle
unit = "p2pool.service"

[onair]
# OnAir server base URL
server = "http://localhost:1920"
# Re-registration interval in seconds (0 = register once)
register_interval = 60

[images]
# Directory containing button images (PNG, will be resized to key dimensions)
dir = "/opt/deckd/images"
```

## Images

User-provided PNGs, sized to Stream Deck Mini key resolution (80×80 pixels). Four images expected in the configured images directory:

- `monero_online.png`
- `monero_offline.png`
- `onair_on.png`
- `onair_off.png`

These are not checked into the repo. The config file points to their location on disk. `.gitignore` the `images/` directory; include an `images/README.md` documenting the expected filenames and dimensions.

No runtime text rendering. Each state maps to exactly one pre-baked image. The `streamdeck` library handles format conversion and resizing to key dimensions internally via its Pillow transitive dependency.

## Systemd Unit

```ini
[Unit]
Description=Stream Deck Daemon
After=network.target p2pool.service

[Service]
Type=simple
User=deckd
Group=deckd
WorkingDirectory=/opt/deckd
ExecStart=/usr/bin/uv run deckd.py --config /opt/deckd/deckd.toml
Restart=always
RestartSec=5

# Needs access to USB HID device
SupplementaryGroups=plugdev input

[Install]
WantedBy=multi-user.target
```

## udev Rules

Same pattern as the existing OnAir sign's `10-usb.rules`, but scoped to Stream Deck:

```
# Elgato Stream Deck Mini
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0063", MODE="0660", GROUP="plugdev"
```

(Verify product ID against the specific Stream Deck Mini revision purchased. The USB-C Mini may use a different product ID than the original USB-A model.)

## Project Structure

```
deckd/
├── deckd.py              # Main daemon entry point
├── config.py             # Config loading (TOML/JSON)
├── pyproject.toml        # Project metadata + dependencies
├── uv.lock               # Locked dependency versions (committed)
├── .python-version       # Python version pin for uv
├── buttons/
│   ├── base.py           # Abstract button class (image update, press handler)
│   ├── p2pool.py         # P2Pool button: D-Bus subscription + toggle
│   └── onair.py          # OnAir button: sign registration + toggle
├── deck.py               # Stream Deck device wrapper (init, key callback routing)
├── http_server.py        # Embedded HTTP listener for OnAir sign pushes
├── images/               # User-provided; not checked in
│   ├── monero_online.png
│   ├── monero_offline.png
│   ├── onair_on.png
│   └── onair_off.png
├── deckd.toml.example
├── install/
│   ├── deckd.service
│   └── 99-streamdeck.rules
└── README.md
```

## `pyproject.toml`

```toml
[project]
name = "deckd"
version = "0.1.0"
description = "Headless Stream Deck daemon for service control"
requires-python = ">=3.11"
dependencies = [
    "streamdeck>=0.9.5",
    "requests>=2.31",
    "dbus-next>=0.2.3",
    "flask>=2.3",
]

[project.scripts]
deckd = "deckd:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Install / lock workflow:

```sh
uv sync          # install from uv.lock (CI, deploy)
uv lock          # regenerate uv.lock after editing pyproject.toml
uv run deckd.py  # run with locked deps, no activate dance
```

`uv.lock` is committed to the repo. `uv sync --frozen` in the systemd `ExecStartPre=` if you want belt-and-suspenders.

## Button Base Class

Each button implements:

```python
class DeckButton(ABC):
    key_index: int

    @abstractmethod
    def get_image_path(self) -> str:
        """Return path to the current PNG for this key."""

    @abstractmethod
    def on_press(self, deck) -> None:
        """Handle key press."""

    @abstractmethod
    def on_release(self, deck) -> None:
        """Handle key release (usually no-op)."""

    def update_display(self, deck) -> None:
        """Push current image to the physical key."""
        image = PILHelper.create_scaled_image(deck, Image.open(self.get_image_path()))
        deck.set_key_image(self.key_index, PILHelper.to_native_format(deck, image))
```

## Future Buttons (slots 2–5)

Reserved for later use. Ideas from this conversation:

- **Button 2:** Print-safe mode — stops P2Pool, shows "SAFE TO PRINT" for 2 minutes, auto-restarts. Combines with Button 0.
- **Button 3:** xmrig hashrate display (read from xmrig's HTTP API, show H/s on key LCD). Press to pause/resume.
- **Button 4–5:** TBD.

Unassigned keys should display a blank/dark image.

## Non-Goals

- No web UI or configuration GUI. Edit the TOML, restart the service.
- No auto-updates. `uv lock` pins everything; update manually with `uv lock --upgrade`.
- No Electron, no Node.js, no Yarn, no fnm.
- No Companion, no OpenDeck, no StreamController.
- No pipenv, no poetry. `uv` only.
- No polling for P2Pool state (use D-Bus subscription).
- No polling for OnAir state (register as a sign, receive pushes).
- No Windows/macOS support. This runs on one specific headless Linux box.

## Open Questions

1. **D-Bus auth model:** Will `pydbus` / `dbus-next` work from a non-root systemd service for `StartUnit`/`StopUnit`? May need a polkit rule. Investigate before committing to D-Bus-only; keep `subprocess.run(["systemctl", ...])` as fallback.
2. **Flask vs lighter HTTP server:** The existing OnAir sign uses Flask. For a 2-route listener embedded in a daemon that's already running an event loop, Flask might be heavy. `http.server` or `aiohttp` could be lighter. But Flask is already a known quantity in the OnAir codebase and the sign contract is proven. Pragmatism over minimalism — use Flask unless there's a concrete problem.
3. **Thread model:** The `streamdeck` library's key callback runs in its own thread. Flask needs its own thread. D-Bus subscription needs an event loop (asyncio or glib). Map out thread/async boundaries before writing code. Likely: main thread runs D-Bus event loop, Flask in a background thread (or use `werkzeug` directly), key callbacks in the streamdeck transport thread with state updates posted to a shared queue.
4. **Stream Deck Mini product ID:** The USB-C revision may report a different product ID than the original USB-A `0063`. The `streamdeck` library's `DeviceManager` handles enumeration regardless, but the udev rule needs the right ID. Run `lsusb` with the device plugged in to confirm the `0fd9:XXXX` pair before writing the rule.
5. **OnAir server location:** Config currently assumes `localhost:1920`. If the OnAir server runs on a different host, the sign registration callback URL needs to use deckd's LAN IP (same `get_local_ip()` logic from the existing sign code).
