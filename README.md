# deckd

Headless Python daemon for an **Elgato Stream Deck Mini**: physical toggles for `p2pool.service` (systemd via D-Bus) and **OnAir** (HTTP sign + PUT), as described in [VISION.md](VISION.md).

> ⚠️ **Just for Me**
> 
> This was built to work on *my* machine where I have two specific things - a systemd unit for `p2pool`, and my [onair](https://github.com/Texarkanine/onair) system.
> It would technically work for you with onair + any number of systemd units... with heavy modification.
> This is a "reference example."

## Quick start (target Linux host)

1. **Clone** this repository on the machine that has the Stream Deck plugged in.

2. **Install [uv](https://docs.astral.sh/uv/)** if needed (single static binary installer is on Astral’s site).

3. **Install dependencies** (uses the committed lockfile):

   ```bash
   cd /path/to/my-streamdeck-drivers
   uv sync --frozen
   ```

4. **Config** — copy `deckd.toml.example` to a path you will pass to `--config`, e.g. `/etc/deckd/deckd.toml`, and edit:

   - `listen_port` — port for the embedded OnAir callback HTTP server. `deckd` binds this to **loopback (`127.0.0.1`) only**; the OnAir server is assumed to run on the same host (co-located deployment).
   - `onair.server` — base URL of your OnAir server.
   - `images.dir` — directory containing the PNG assets (see `images/README.md`).
   - `[p2pool].deactivating_*` — filenames and blink interval while `p2pool.service` is in **deactivating** (defaults in `deckd.toml.example`). Extra presses while still deactivating are **ignored** by default. Set optional **`deactivating_escalate_signal`** (1–64, e.g. **9** for SIGKILL) to send **`KillUnit`** on repeat presses; that path still does **not** start or restart the service.

5. **Images** — add `monero_online.png`, `monero_offline.png`, the two deactivating blink frames (`deactivating_image_a` / `b` in config), and `onair_on.png`, `onair_off.png` (80×80 recommended).

6. **udev** — allow the service user to open the USB device:

   ```bash
   sudo cp install/udev/99-streamdeck.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

   Confirm the Stream Deck’s `idVendor` / `idProduct` with `lsusb` (example Mini: `0fd9:0063`).

7. **systemd** — copy and edit the unit, then enable it:

   ```bash
   sudo cp install/systemd/deckd.service /etc/systemd/system/
   sudoedit /etc/systemd/system/deckd.service   # WorkingDirectory, ExecStart, User, Group
   sudo systemctl daemon-reload
   sudo systemctl enable --now deckd.service
   ```

   The sample unit assumes:

   - Repo checkout at `/opt/deckd/deckd`
   - Config at `/etc/deckd/deckd.toml`
   - A dedicated Unix user `deckd` in group `plugdev` (create with `useradd` / `usermod` as needed)

8. **P2Pool / polkit** — an unprivileged user cannot start or stop system units by default; you will see `Interactive authentication required` and a polkit prompt in logs. Which configuration file to install depends on your polkit version — polkit changed its authorization backend between 0.105 and 0.106:

   - **polkit ≤ 0.105** (e.g. Ubuntu 22.04, which ships `0.105-33ubuntu0.x`): uses the **Local Authority** backend and reads **`.pkla`** files. The newer `rules.d/*.rules` JavaScript files are **ignored**.
   - **polkit ≥ 0.106**: uses **JavaScript rules** under `/etc/polkit-1/rules.d/`. `.pkla` files are ignored.

   **Check your version:**

   ```bash
   pkaction --version                          # prints the polkit version
   apt list --installed 2>/dev/null | grep polkitd   # Debian/Ubuntu
   journalctl -u polkit -b | grep 'authority implementation'
   ```

   The journal line looks like `using authority implementation 'local' version '0.105'` on the older backend.

   **polkit ≤ 0.105 (`.pkla`)** — copy and edit the identity:

   ```bash
   sudo cp install/polkit/deckd-p2pool.pkla /etc/polkit-1/localauthority/50-local.d/
   sudoedit /etc/polkit-1/localauthority/50-local.d/deckd-p2pool.pkla   # set Identity=unix-user:<your user>
   sudo systemctl restart polkit
   ```

   Note: `.pkla` filters only by action, not by unit name; this grants the user D-Bus `manage-units` authority for **any** unit. For user-plus-unit scoping you need polkit ≥ 0.106.

   **polkit ≥ 0.106 (`rules.d/*.rules`)** — copy and edit the subject:

   ```bash
   sudo cp install/polkit/99-deckd-p2pool.rules /etc/polkit-1/rules.d/
   sudoedit /etc/polkit-1/rules.d/99-deckd-p2pool.rules   # set subject.user to your account
   sudo systemctl restart polkit
   ```

   Group-based checks (`subject.isInGroup("…")`) are also possible in JS rules. Unit-scoped filtering via `action.lookup("unit") == "p2pool.service"` works on some systemd versions but not all — confirm before relying on it (`journalctl -u polkit` with `polkit.log(...)` in the rule).

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
