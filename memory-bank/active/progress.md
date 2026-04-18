# Progress

## Task summary

Implement the `deckd` Stream Deck daemon per `VISION.md`, with systemd deployment support and uv-managed dependencies. Target server: Ubuntu 22.04, `p2pool.service`, Elgato Stream Deck Mini `0fd9:0063`.

**Complexity:** Level 2 (rework — see "Rework — PR feedback triage" section below)

_Original task complexity: Level 3 — see phase log._

## Phase log

- **Complexity analysis** — Level 3 (multi-component feature: HID deck, D-Bus, HTTP sign, systemd).
- **Plan** — Complete (see `tasks.md`).
- **Preflight** — PASS.
- **Build** — Implemented Python package `deckd/`, tests, `uv.lock`, install artifacts, README; pytest passing locally.
- **QA** — PASS. Operator confirmed `deckd.service` working on target server (kinglear). One trivial doc fix: stale install path + nonexistent `use_sudo_for_systemctl`/sudoers reference in `install/polkit/99-deckd-p2pool.rules`. 16/16 tests passing.
- **Reflect** — Complete. See `memory-bank/active/reflection/reflection-deckd-initial.md`. Persistent files reconciled: `productContext.md`, `techContext.md`, `systemPatterns.md`.

## Rework — PR feedback triage

Operator-approved rework scope (after triaging 11 PR comments; see chat). Accepted fixes only:

1. **`__main__.py`** — bind Flask to loopback (`127.0.0.1`) by default. deckd and the OnAir server run on the same host, so loopback is correct and closes unnecessary LAN exposure.
2. **`__main__.py` `register_loop`** — `register_sign` uses blocking `requests` with a 10s timeout; calling it inline stalls the asyncio loop (delays D-Bus `PropertiesChanged` delivery). Move to `asyncio.to_thread(...)`.
3. **`buttons/onair.py` `on_press`** — blocking `put_state` currently runs on the HID callback thread; a stalled OnAir server blocks *all* further keypresses for up to 10s. Mirror `p2pool.py`'s `asyncio.run_coroutine_threadsafe` pattern.
4. **`systemd_unit.py` systemctl fallback** — `subprocess.run` inside async functions blocks the event loop. Wrap the three `systemctl_*` helpers in `asyncio.to_thread(...)` and make them async; update callers.
5. **`systemd_unit.py` D-Bus subscription** — add a one-time `Manager.Subscribe()` call at startup so `PropertiesChanged` delivery is guaranteed-correct per systemd docs (currently works by incidental touch of the unit). Add a done-callback to the task created from `on_change(value)` so exceptions log via `logger.exception` instead of surfacing as "Task exception was never retrieved".
6. **`tests/test_config.py`** — escape the `.` in `pytest.raises(match=".service")` regex so the assertion matches the literal substring.

Explicitly rejected (and why, for the record):

- Expose-to-LAN opt-in guard (#1 as originally proposed) — superseded by loopback default above.
- Per-button toggle lock on `p2pool.py` — would defeat the deliberate "press harder to escalate" UX (`deactivating_escalate_signal`).
- NaN/Inf guard in `config.py` float validators — defending against self-inflicted config errors; not worth the code.
- `key_callback` generic threadpool dispatcher — wrong layer; fix #3 at the button.
- Shared-secret / allowlist auth on `http_server.py` PUT — OnAir protocol has no such credential; adding one breaks interop for no benefit on a trusted LAN host.
- `techContext.md` "Python 3.11+" fix — already resolved during the reflect-phase persistent-file reconciliation.

## Rework phase log

- **Plan** — Complete. 11 ordered steps in `tasks.md`; 7 testable behaviors across two new test files (`tests/test_onair_button.py`, `tests/test_systemd_unit.py`); no new deps.
- **Preflight** — PASS (with advisory). Convention / dependency / conflict / completeness all clean. Advisory: a shared `run_coroutine_threadsafe + done-callback logger` helper would DRY the soon-to-be-duplicated pattern across `P2PoolButton` and `OnAirButton` — not mandated (two sites; surgical diff preferred on a rework PR).
- **Build** — Complete. All 11 steps landed to plan, no deviations. Full test suite 25/25 green (16 pre-existing + 9 new: 2 in `test_onair_button.py`, 7 in `test_systemd_unit.py`); no lint errors; preflight advisory deliberately not taken (pattern kept inlined across the two button classes). Advisory to keep on the radar for QA: the `Manager.Subscribe()` path and the loopback Flask bind are not covered by unit tests — both will be validated on target host (`kinglear`) during QA.
- **QA** — PASS. Semantic review found one stylistic inconsistency (`_log_exc(f: Any)` in `OnAirButton.on_press` vs `_log_exc(f: asyncio.Future[Any])` in `P2PoolButton.on_press`); normalized to match the neighbor. No blocking findings. KISS/DRY/YAGNI/Completeness/Regression/Integrity/Documentation all clean. Test suite still 25/25, lint clean. Out-of-band verification items for operator host validation: (a) `manager.call_subscribe()` succeeds on target systemd, (b) Flask loopback bind still reachable from co-located OnAir server, (c) `systemctl` fallback path still works under async conversion.
- **Reflect** — Complete. See `memory-bank/active/reflection/reflection-deckd-rework-pr1.md`. Persistent-file reconciliation: `systemPatterns.md` gained a new pattern about `Manager.Subscribe()` being required for spec-correct `PropertiesChanged` delivery (the concurrency paragraph was already added during build step 10). `productContext.md` and `techContext.md` unchanged — rework introduced no audience/use-case/benefit/constraint shift and no new deps or tools.
- **Post-reflect hotfix** — Operator caught on target host that the OnAir button stopped receiving pushes. Root cause: the rework bound Flask to `127.0.0.1` but `register_sign` was still registering `http://<guess_primary_ipv4()>:PORT/...` as deckd's callback URL with the OnAir server — so OnAir tried to POST to the host's LAN IP and got "connection refused" (the listener is only on loopback). Fix: hardcode `callback_base = f"http://127.0.0.1:{listen_port}"`; `deckd/netutil.py::guess_primary_ipv4` is now dead code and was removed. Test suite still 25/25 green; no test change required (no test covered the callback URL construction). Operator-to-validate on host: `systemctl restart deckd && journalctl -u deckd -n 50` shows a successful re-register and OnAir pushes resume reaching the button. This is a rework-scope miss on my part — the loopback bind decision should have included the callback-URL side in the same breath. Lesson captured as a build/QA checklist item: when a bind address changes, audit every outbound reference to the old address in the same diff.
