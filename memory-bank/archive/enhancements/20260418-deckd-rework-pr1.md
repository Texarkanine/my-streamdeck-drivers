---
task_id: deckd-rework-pr1
complexity_level: 2
date: 2026-04-18
status: completed
---

# TASK ARCHIVE: deckd rework — PR feedback hardening

## SUMMARY

Shipped six accepted PR-feedback fixes on top of `deckd-initial`: loopback Flask bind (`127.0.0.1`), `register_sign` and `put_state` moved off the asyncio loop / HID callback thread via `asyncio.to_thread` and `asyncio.run_coroutine_threadsafe`, async `systemctl_*` fallbacks over `asyncio.to_thread(subprocess.run, …)`, one-time `Manager.Subscribe()` at startup, done-callback on D-Bus `ActiveState` handler tasks so exceptions log via `logger.exception`, and a tightened `.service` regex in config tests. Added nine tests (`tests/test_onair_button.py`, `tests/test_systemd_unit.py`); full suite ended at 25 passing. After deploy, the operator found OnAir pushes broken: Flask listened on loopback but `register_sign` still advertised the LAN IP as the callback URL. Fixed by registering `http://127.0.0.1:{port}` and removing `deckd/netutil.py`.

## REQUIREMENTS

Targeted the six accepted rework items from triaged PR feedback (async hygiene, loopback listener, systemd subscription correctness, test regex). Explicitly out of scope: LAN-exposure toggles, per-button locks, NaN guards, generic key dispatcher, HTTP PUT secrets, etc.

## IMPLEMENTATION

**OnAir:** `OnAirButton` takes keyword-only `loop`; `on_press` schedules `_dispatch` on the main loop with `run_coroutine_threadsafe`, runs `put_state` in `asyncio.to_thread`, mirrors `P2PoolButton` done-callback logging.

**Main:** Flask `run_flask_in_thread(..., "127.0.0.1", port)`; after `get_manager_interface`, `try: await manager.call_subscribe()` with log-and-continue on failure; `register_loop` uses `await asyncio.to_thread(register_sign, …)`; callback base URL `http://127.0.0.1:{listen_port}` (post-hotfix).

**systemd_unit:** `systemctl_kill`, `systemctl_start`, `systemctl_stop` are `async` wrappers around `asyncio.to_thread(subprocess.run, …)`; `try_kill_unit` / `try_start_stop` await them; `subscribe_active_state_changes` adds `task.add_done_callback` to log handler failures.

**Tests / docs:** New pytest modules as above; `tests/test_config.py` uses `match=r"\.service"`; README and `memory-bank/systemPatterns.md` updated for concurrency and `Manager.Subscribe()` pattern.

## TESTING

`uv run pytest` — 25/25 before hotfix; same after callback-URL fix. QA semantic pass (stylistic nit on Future annotation). Target host (`kinglear`) validated loopback listener with `netstat`/`curl`; operator confirmed OnAir button after callback URL fix.

## LESSONS LEARNED

Surgical plans and unit tests clear each named step but do not automatically catch **adjacent** coupling: binding the listener to loopback without updating every string that tells another process how to reach that listener broke co-located OnAir until the callback host matched the bind. A bind address and any advertised peer-facing URL are one logical change.

Cross-thread asyncio tests should drain pending tasks before `loop.stop()` to avoid spurious "Task was destroyed" warnings when `asyncio.to_thread` unwinds after the worker returns.

`asyncio.run_coroutine_threadsafe` yields a `concurrent.futures.Future`; existing code annotates `asyncio.Future[Any]` for duck-typing consistency — fine until strict typing.

## PROCESS IMPROVEMENTS

When changing bind addresses, URLs, or ports: grep the repo for consumers of the old address in the **same change** (plan step should include evidence). For I/O boundary rework, add at least one test that crosses the boundary (e.g. register payload or callback URL construction vs actual bind), not only mocks of internals.

## TECHNICAL IMPROVEMENTS

Optional follow-up: a small integration or contract test that asserts the registered callback host matches the Flask bind address (or reads both from one source of truth). Optional: extract shared `schedule_and_log` only if a third HID→async dispatch site appears.

## NEXT STEPS

None required for this task. Optional: add callback/bind contract test if similar rework touches networking again.

---

## Inlined reflection notes (ephemeral source: `reflection-deckd-rework-pr1.md`)

The reflection expanded on **Post-Reflect Hotfix**: operator saw OnAir stop updating; deckd on `127.0.0.1:5111`, OnAir elsewhere on host; LAN `curl` to `:5111` refused as expected for loopback-only; root cause was `guess_primary_ipv4()` in the registered callback URL. Fix aligned URL with bind and deleted `netutil.py`.

**Million-dollar framing:** if thread-safety and “no blocking on wrong thread” had been system invariants from day one, much of the rework would have been unnecessary; `systemPatterns.md` now documents the concurrency model for future buttons.

**Process insights:** preflight helped validate touchpoints (`call_subscribe` naming, async callers) but not cross-step gaps; test plans that only cover explicitly named behaviors miss implicit couplings.
