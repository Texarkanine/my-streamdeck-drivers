# Task: deckd rework — PR feedback hardening

* Task ID: deckd-rework-pr1
* Complexity: Level 2
* Type: rework / correctness & async hygiene

Apply six accepted PR-feedback fixes to the shipped `deckd-initial` build.
Scope is strictly the delta below. Context: deckd and the OnAir server run
on the same host on a trusted LAN; no LAN-scale or multi-tenant threat
model applies.

Accepted scope:

1. Default-bind the Flask listener to `127.0.0.1` (co-located with OnAir).
2. Move `register_sign` off the asyncio event loop via `asyncio.to_thread`.
3. Move `OnAirButton.on_press`'s `put_state` off the HID callback thread
   via `asyncio.run_coroutine_threadsafe` + `asyncio.to_thread` (mirroring
   `P2PoolButton`).
4. Convert `systemctl_kill/start/stop` to `async` wrappers over
   `asyncio.to_thread(subprocess.run, …)`; update async callers
   (`try_kill_unit`, `try_start_stop`) to `await`.
5. Call `Manager.Subscribe()` once at startup so
   `PropertiesChanged` delivery is spec-correct; add a done-callback to
   the task spawned inside `subscribe_active_state_changes` so handler
   exceptions surface via `logger.exception` instead of Python's "Task
   exception was never retrieved" warning.
6. Escape the dot in `tests/test_config.py` line 129 regex
   (`.service` → `\.service`).

Rejected scope (captured in `progress.md`): LAN-exposure opt-in, per-button
toggle lock, NaN/Inf config guard, `key_callback` generic dispatcher,
HTTP PUT shared-secret, stale `techContext.md` "Python 3.11+" (already
resolved during reflect-phase reconciliation).

## Test Plan (TDD)

### Behaviors to Verify

Test coverage is proportional to value: some fixes are wiring-trivial
(hardcoded-constant change, regex escape) and do not justify a new test
beyond the existing suite.

- **OnAirButton.on_press returns promptly even when the HTTP call is
  slow**: given a `put_state` that blocks for ≥0.3s, `on_press` returns
  in <50ms on the caller thread → verifies the callback-thread unblock
  fix. New test in `tests/test_onair_button.py`.
- **OnAirButton.on_press dispatches the PUT via the provided loop**:
  pressing a button with a mocked `put_state` eventually (≤1s) results
  in `put_state` being called with the flipped state → verifies the
  dispatched coroutine actually runs. Same new test file.
- **`systemctl_kill/start/stop` are coroutines and invoke
  `subprocess.run` via `asyncio.to_thread`**: calling each with a mocked
  `subprocess.run` returns a coroutine; awaiting it invokes
  `subprocess.run` with the expected argv (`systemctl kill -s N unit`
  / `systemctl start unit` / `systemctl stop unit`) exactly once.
  New test file `tests/test_systemd_unit.py`.
- **`try_start_stop` / `try_kill_unit` fallback paths await the async
  `systemctl_*`**: when `bus=None` or D-Bus raises, the async
  `systemctl_*` is awaited (not called sync) and completes. Same file.
- **Exception in D-Bus on-change handler surfaces via logger**: fire
  `subscribe_active_state_changes`'s property-changed handler with a
  handler coroutine that raises; the scheduled task's exception is
  logged via `logger.exception` (captured via `caplog`). New test in
  `tests/test_systemd_unit.py`.
- **Existing `tests/test_config.py` `.service` regex escape change
  keeps the test green**: no behavior change, but the pattern now
  matches only the literal `.service` substring.
- **No regression in existing tests**: `test_config.py`,
  `test_http_server.py`, `test_onair_client.py`, `test_p2pool_button.py`,
  `test_p2pool_press_kind.py` continue to pass 16/16 + new.

### Edge Cases

- `OnAirButton` with no running loop: constructor still requires a
  `loop`, matching `P2PoolButton`'s signature; callers in `__main__`
  already have one. No default-loop discovery.
- `put_state` raising inside the worker thread: exception is logged by
  `onair_client.put_state` itself (existing behavior), and the
  `run_coroutine_threadsafe` future's done-callback logs it again at the
  button layer; no unhandled-exception warnings.
- `Manager.Subscribe()` failing: log and continue — current code works
  without it on this systemd version; it's a reliability upgrade, not a
  prerequisite.
- `subscribe_active_state_changes` `on_change` raising: caught via
  `Task.add_done_callback` → `logger.exception`.

### Test Infrastructure

- Framework: **pytest** (+ `pytest-asyncio` in `asyncio_mode = "auto"`),
  configured in `pyproject.toml`.
- Test location: `tests/`.
- Conventions: `test_<module>.py`, flat structure, no fixtures dir,
  `unittest.mock.patch`/`MagicMock` for mocking. Async tests are plain
  `async def test_…` thanks to `asyncio_mode = "auto"`.
- New test files: `tests/test_onair_button.py`,
  `tests/test_systemd_unit.py`.

## Implementation Plan

Ordered so each step is testable on its own and subsequent steps don't
require backtracking.

1. **Add `loop` parameter to `OnAirButton`**
   - Files: `deckd/buttons/onair.py`.
   - Changes: extend `__init__` to take a required keyword-only
     `loop: asyncio.AbstractEventLoop`; store as `self._loop`. No
     behavior change yet.

2. **Update `__main__` to pass `loop` into `OnAirButton`**
   - Files: `deckd/__main__.py`.
   - Changes: `OnAirButton(1, cfg.images.dir, cfg.onair.server, onair_state.get, loop=loop)`.

3. **Switch `OnAirButton.on_press` to scheduled dispatch (TDD)**
   - Files: `deckd/buttons/onair.py`,
     new `tests/test_onair_button.py`.
   - Changes: write failing tests first —
     (a) `on_press` returns in <50ms when `put_state` sleeps 0.3s,
     (b) after a short wait, the mocked `put_state` was called with
     the flipped state.
     Then implement: replace the inline `put_state` call with an inner
     `async def _dispatch(new_state)` that does
     `await asyncio.to_thread(put_state, self._onair_server, new_state)`;
     schedule via `asyncio.run_coroutine_threadsafe(_dispatch(new_state), self._loop)`
     and attach a done-callback that logs `f.exception()` via
     `logger.exception`, mirroring `P2PoolButton.on_press`.

4. **Move `register_sign` off the event loop**
   - Files: `deckd/__main__.py`.
   - Changes: in `register_loop`, replace the inline call with
     `await asyncio.to_thread(register_sign, cfg.onair.server, callback_base)`.
     Keep the existing `try/except Exception: logger.exception(...)` wrapping
     and the interval-sleep/return logic. No new test (existing
     `test_onair_client.py` already covers `register_sign` itself).

5. **Bind Flask to loopback by default**
   - Files: `deckd/__main__.py`.
   - Changes: `run_flask_in_thread(app, "127.0.0.1", cfg.general.listen_port)`.
     No test. Update README quick-start note that said "must be reachable
     from the OnAir server" to note co-location on the same host.

6. **Convert `systemctl_kill/start/stop` to async + update callers (TDD)**
   - Files: `deckd/systemd_unit.py`, new `tests/test_systemd_unit.py`.
   - Changes: failing tests first —
     (a) `systemctl_kill("p2pool.service", 9)` is awaitable and, when
     awaited with `subprocess.run` mocked, calls
     `subprocess.run(["systemctl", "kill", "-s", "9", "p2pool.service"], check=True)` once;
     (b) same shape for `systemctl_start` and `systemctl_stop`;
     (c) `try_start_stop(bus=None, unit, want_active=True)` awaits
     `systemctl_start` (verify via patching the async helper);
     (d) `try_kill_unit(bus=None, unit, 15)` awaits `systemctl_kill`.
     Then implement: make the three `systemctl_*` helpers
     `async def`, body
     `await asyncio.to_thread(subprocess.run, [...], check=True)`;
     update `try_kill_unit` to `await systemctl_kill(unit, signal)`
     and `try_start_stop` to `await systemctl_start/stop(unit)`.
     No timeout added (rejected per triage — would introduce a new
     failure mode without a clear benefit).

7. **Call `Manager.Subscribe()` at startup**
   - Files: `deckd/__main__.py`.
   - Changes: after `manager = await get_manager_interface(bus)` and
     before subscribing, add
     `try: await manager.call_subscribe() \n except Exception: logger.exception("Manager.Subscribe failed; continuing")`.
     No unit test (heavy MessageBus mocking for low value); validated on
     target host during QA.

8. **Done-callback in `subscribe_active_state_changes` (TDD)**
   - Files: `deckd/systemd_unit.py`, `tests/test_systemd_unit.py`.
   - Changes: failing test first — fire `_handler` (or the bound
     `on_properties_changed` handler) with a handler coroutine that
     raises `RuntimeError("boom")`; after an `await asyncio.sleep(0)`
     the logger receives an `exception`-level record containing
     `"boom"` (via `caplog`).
     Then implement: change `loop.create_task(on_change(value))` to
     bind the task and register
     `task.add_done_callback(_log_task_exc)` where
     `_log_task_exc(t)` calls
     `logger.exception("ActiveState change handler failed", exc_info=t.exception())`
     when `t.exception() is not None`.

9. **Escape regex dot in `tests/test_config.py`**
   - Files: `tests/test_config.py`.
   - Changes: `match=".service"` → `match=r"\.service"` on line 129.

10. **Documentation sweep**
    - Files: `README.md`, `memory-bank/systemPatterns.md`.
    - Changes:
      - `README.md`: update step 4 to note `listen_port` is now a
        loopback-only listener (OnAir server runs on the same host).
      - `memory-bank/systemPatterns.md`: add a sentence under the
        concurrency section noting that every blocking I/O call (HTTP,
        `subprocess.run`) is bounced off the asyncio loop / HID thread
        via `asyncio.to_thread` / `asyncio.run_coroutine_threadsafe`.
    - `deckd.toml.example` and other install artifacts: no change
      required (no new config keys introduced).

11. **Run the full test suite**
    - Command: `uv run pytest`.
    - Expectation: 16 existing + new tests, all green.

## Technology Validation

No new dependencies. No build-tool changes. Only stdlib (`asyncio`,
`subprocess`) and existing project deps (`dbus-next`, `requests`).
**No new technology — validation not required.**

## Dependencies

- `asyncio` (stdlib) — `to_thread`, `run_coroutine_threadsafe`.
- `dbus-next` (existing) — `Manager.Subscribe()` is an already-exposed
  method via the introspected Manager interface; no new library.

## Challenges & Mitigations

- **`OnAirButton` constructor signature change** may look like a
  breaking API change — but the only caller is `deckd/__main__.py`, and
  the class has no public consumers outside the package. Mitigation:
  update the one call site in step 2, mirror the already-existing
  `P2PoolButton(loop=…)` convention so the shape is familiar.
- **Timing-based test for "returns promptly"** can be flaky on a busy
  CI host. Mitigation: use a generous tolerance (50ms budget against a
  0.3s blocking call); the real assertion is ~10× slack, not a tight
  benchmark.
- **`Manager.Subscribe` across `dbus-next` versions** — the method is
  on the standard systemd Manager interface; `call_subscribe` follows
  the library's `call_<lower_snake_case>` convention. Mitigation: wrap
  in `try/except` and log — current code already works without it on
  this host, so the call failing isn't a regression.
- **`caplog` in async tests**: `pytest-asyncio` in `asyncio_mode = "auto"`
  handles `caplog` the same as sync tests. Mitigation: if the log
  capture is shaky, fall back to a module-level logger handler attached
  in the test and assert on records directly.

## Status

- [x] Initialization complete
- [x] Test planning complete (TDD)
- [x] Implementation plan complete
- [x] Technology validation complete
- [x] Preflight (PASS with advisory)
- [ ] Build
- [ ] QA
