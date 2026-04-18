# Project Brief

## User Story

As an operator of a headless Ubuntu mining/P2Pool host, I want a USB Stream Deck Mini to show P2Pool and OnAir state and let me toggle them, so I can control services without SSH and stay in sync with OnAir pushes.

## Use-Case(s)

### Use-Case 1 — Deploy from git

Clone the repository on the server, run `uv sync` (or equivalent) to install locked dependencies, copy and adjust the example systemd unit and config, install udev rules, place PNG assets, enable and start `deckd.service`.

### Use-Case 2 — P2Pool key

Display `monero_online.png` / `monero_offline.png` based on `p2pool.service` `ActiveState` (via D-Bus subscription, not polling). On press, start or stop the unit via D-Bus with a documented `systemctl` fallback if authorization fails.

### Use-Case 3 — OnAir key

Register as a sign with the OnAir server; run an embedded HTTP listener for GET/PUT `/onair/api/v1/state`; update the key image from pushes and allow toggling via PUT; re-register periodically.

## Requirements

1. Implement `deckd` per `VISION.md` (architecture, buttons, config shape, non-goals).
2. Ship `uv` + `pyproject.toml` + committed `uv.lock`.
3. Ship example `deckd.toml`, `install/deckd.service`, and udev rules (Stream Deck Mini `0fd9:0063` confirmed on target).
4. Document install steps: clone, `uv sync`, configure paths, systemd enable/start, images directory.
5. **systemd**: `Restart=always`, start on boot (`WantedBy=multi-user.target`), suitable for production.
6. Target host: **Ubuntu 22.04**, **Python 3.10.12** system — runtime must work with `requires-python` and `uv` (document if a newer Python is pulled by `uv`).

## Constraints

- Integration testing on real hardware is **only on the operator’s machine**; CI/local runs use mocks.
- No GUI, no Node stack.

## Acceptance Criteria

1. `uv sync` installs the package and locked deps; `uv run deckd --config …` starts (hardware-dependent paths may fail without device).
2. Unit tests cover config loading, OnAir HTTP contract, and core button logic with mocks.
3. Example systemd unit and README describe copy-edit-enable workflow.
4. `images/README.md` lists required PNG names and 80×80 size; `images/` gitignored.
