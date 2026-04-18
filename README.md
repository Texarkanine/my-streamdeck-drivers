# deckd

Headless Python daemon for an **Elgato Stream Deck Mini**: physical toggles for `p2pool.service` (systemd via D-Bus) and **OnAir** (HTTP sign + PUT), as described in [VISION.md](VISION.md).

## Quick start (target Linux host)

1. **Clone** this repository on the machine that has the Stream Deck plugged in.

2. **Install [uv](https://docs.astral.sh/uv/)** if needed (single static binary installer is on Astral’s site).

3. **Install dependencies** (uses the committed lockfile):

   ```bash
   cd /path/to/my-streamdeck-drivers
   uv sync --frozen
   ```

4. **Config** — copy `deckd.toml.example` to a path you will pass to `--config`, e.g. `/etc/deckd/deckd.toml`, and edit:

   - `listen_port` — port for the embedded OnAir callback HTTP server (must be reachable from the OnAir server for sign registration).
   - `onair.server` — base URL of your OnAir server.
   - `images.dir` — directory containing the four PNGs (see `images/README.md`).

5. **Images** — add `monero_online.png`, `monero_offline.png`, `onair_on.png`, `onair_off.png` (80×80 recommended) to the configured images directory.

6. **udev** — allow the service user to open the USB device:

   ```bash
   sudo cp install/99-streamdeck.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

   Confirm the Stream Deck’s `idVendor` / `idProduct` with `lsusb` (example Mini: `0fd9:0063`).

7. **systemd** — copy and edit the unit, then enable it:

   ```bash
   sudo cp install/deckd.service /etc/systemd/system/
   sudoedit /etc/systemd/system/deckd.service   # WorkingDirectory, ExecStart, User, Group
   sudo systemctl daemon-reload
   sudo systemctl enable --now deckd.service
   ```

   The sample unit assumes:

   - Repo checkout at `/opt/deckd/deckd`
   - Config at `/etc/deckd/deckd.toml`
   - A dedicated Unix user `deckd` in group `plugdev` (create with `useradd` / `usermod` as needed)

8. **Permissions** — toggling `p2pool.service` requires authorization for `StartUnit`/`StopUnit` on the system bus. If D-Bus calls are denied, check polkit rules or use a documented `systemctl` NOPASSWD/sudo fallback (see [VISION.md](VISION.md) open questions).

## Run without systemd (debug)

```bash
uv run deckd --config /path/to/deckd.toml
```

## Development

Python **3.10+** (see `.python-version`; Ubuntu 22.04 ships 3.10).

```bash
uv sync --extra dev
uv run pytest
```

If `uv sync` fails to resolve packages because extra package indexes pin old wheels, this repo sets `[tool.uv] index-strategy = "unsafe-best-match"` in `pyproject.toml` so PyPI can satisfy versions. Adjust if your security policy requires a different strategy.

## Testing

Automated tests cover config loading and the OnAir HTTP routes. **USB, D-Bus, and OnAir integration** must be validated on the real host (this environment does not have your hardware or services).
