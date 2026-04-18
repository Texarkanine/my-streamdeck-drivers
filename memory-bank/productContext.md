# Product Context

## Target Audience

Operators of a headless Linux server who want physical USB buttons (Elgato Stream Deck Mini) to toggle local services and mirror on-air state—without a display server, GUI, or companion apps.

## Use Cases

- Toggle `p2pool.service` via systemd and show its active/inactive state on a dedicated key with pre-baked PNGs.
- Act as an OnAir **sign**: register with an OnAir HTTP API, receive pushed state updates, and toggle on-air state via HTTP—keeping the deck key in sync with other clients.
- Run reliably in the background on a single dedicated box (mining / P2Pool host).

## Key Benefits

- Event-driven updates: systemd unit state via D-Bus subscription; OnAir via server push (no polling loops for those concerns).
- Simple operations model: configuration file on disk, restart to apply; no web UI for config.
- Locked dependencies via `uv` and a committed lockfile.

## Success Criteria

- Daemon talks to the Stream Deck over USB, renders the correct images per state, and handles key presses.
- P2Pool key reflects `p2pool.service` state and can start/stop the unit (subject to host permissions).
- OnAir key registers, receives pushes, serves the sign HTTP contract, and can PUT state changes.
- Deployment docs cover systemd, permissions, udev for the device, and image assets.

## Key Constraints

- Headless Linux only; no Windows/macOS support in scope.
- Python floor pinned in `pyproject.toml` (Ubuntu 22.04 system Python), `uv` for environment and locking; no pipenv/poetry.
- No Node/Electron/Companion/OpenDeck for this stack.
- User-supplied PNGs (e.g. 80×80 for Mini); not checked into the repo by default.
- Real hardware integration and permission models must be validated on the target host (USB IDs, polkit, service user).
