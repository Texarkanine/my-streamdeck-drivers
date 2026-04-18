---
task_id: deckd-rework-pr1
date: 2026-04-18
complexity_level: 2
---

# Reflection: deckd PR-feedback hardening rework

## Summary

Landed six accepted PR-feedback fixes on top of the shipped `deckd-initial`
build: loopback Flask bind, every blocking `requests`/`subprocess.run`
call bounced off the asyncio loop / HID thread, `Manager.Subscribe()` at
startup, done-callback that logs handler exceptions, and a tightened
`pytest.raises` regex. 25/25 tests green, no new deps, no behavior
change to the happy path — **except** for the one hardware-visible
regression the plan and test matrix both missed (see "Post-Reflect
Hotfix" below).

## Requirements vs Outcome

All six accepted rework requirements from `projectbrief.md` /
`tasks.md` were delivered, no scope added, no scope dropped. The six
explicitly-rejected PR comments (LAN opt-in, per-button toggle lock,
NaN/Inf config guard, `key_callback` generic dispatcher, HTTP PUT
shared-secret, `techContext.md` stale-fact) stayed rejected; rejection
rationale remains recorded in `progress.md` for future-me.

## Plan Accuracy

Plan held verbatim. The 11 ordered steps built on each other without
reordering or splits, and the two TDD test files (`tests/test_onair_button.py`,
`tests/test_systemd_unit.py`) landed with the shape the plan
described: 2 + 7 tests, one caller-path test per `systemctl_*` helper,
one `caplog` test for the done-callback. The challenges the plan
flagged (timing-based test flakiness, `caplog` in async mode,
`dbus-next` method-name convention for `Subscribe`) were all either
non-issues or handled as the mitigations described.

The only deviation from plan was cosmetic: the initial slow-`put_state`
test tore down the loop while `asyncio.to_thread`'s epilogue was still
running on the main task, producing a `Task was destroyed but it is
pending!` warning in pytest output. Added a small `_stop_loop_cleanly`
helper that drains `asyncio.all_tasks(loop)` before calling
`loop.stop()`. Useful pattern for future cross-thread tests.

## Build & QA Observations

Build was a clean walk down the plan *as written*; each step was
independently testable and red-green'd without surprises. QA caught
exactly one stylistic nit (`_log_exc(f: Any)` vs the sibling's
`f: asyncio.Future[Any]`) which is exactly the kind of low-cost
consistency find that belongs in the post-build semantic review, not
in code review later.

**However**, the Build/QA cleanness claim is only honest-within-scope.
The scope itself had a half-step gap: the loopback-bind step changed
the *listener* address but left `register_sign`'s advertised callback
URL pointing at the host's LAN IP. Hardware deployment caught the
mismatch immediately (OnAir pushes → connection refused at the LAN
IP) — the test suite never exercised it because no test covered the
callback-URL construction in `__main__.py::register_loop`. See
"Post-Reflect Hotfix" below.

Preflight's advisory call — "keep the `run_coroutine_threadsafe +
done-callback` pattern inlined across two buttons instead of
extracting a helper" — was the right call on a rework PR. The five
lines of boilerplate mirror exactly between `P2PoolButton.on_press`
and `OnAirButton.on_press`; a shared `schedule_and_log` helper would
trade one grep-friendly idiom for one level of indirection. Revisit if
a third caller ever shows up.

## Post-Reflect Hotfix

Operator ran the rework build on the target host (`kinglear`) and the
OnAir button stopped reflecting pushed state. `sudo netstat -tlnp`
confirmed deckd listening on `127.0.0.1:5111` (as planned) and the
OnAir server on `0.0.0.0:1920` on the same host. `curl` from the LAN
IP failed with `connection refused`, which is the expected behavior
of a loopback-only listener — so the bind was correct.

The bug was upstream of the listener: `register_sign`
in `deckd/__main__.py::register_loop` was building the callback URL
as `f"http://{guess_primary_ipv4()}:{port}"`, so OnAir was registered
with `http://192.168.1.122:5111/...` as the push target. OnAir (even
co-located) then tried to POST there and hit `connection refused`.

Fix (one commit after reflect): hardcode the callback host to
`127.0.0.1` to match the bind, and delete `deckd/netutil.py` which
existed solely to compute the now-unwanted LAN IP. No test change
(no test covered this construction path).

## Insights

### Technical

- **`asyncio.run_coroutine_threadsafe` returns a `concurrent.futures.Future`,
  not an `asyncio.Future`** — the two have compatible `.exception()` /
  `.add_done_callback()` surfaces, so duck-typed code works fine. The
  existing `P2PoolButton._log_exc` annotates `f: asyncio.Future[Any]`,
  which is technically wrong but stylistically established. The new
  `OnAirButton._log_exc` now mirrors it for in-codebase consistency;
  flag this if either annotation ever ends up in a type-checker's path.
- **Test teardown in cross-thread tests needs to drain the loop**, not
  just stop it. `asyncio.to_thread` resumes the awaiting coroutine
  back on the loop after the worker thread returns; if the loop has
  been stopped by then, the task dies with a warning. Pattern that
  works: schedule a `_drain()` coroutine via `run_coroutine_threadsafe`,
  wait on its result, *then* `loop.call_soon_threadsafe(loop.stop)`.
- **A bind address and any address advertised back to a peer are a
  pair, not two independent knobs.** Changing the listener from
  `0.0.0.0` to `127.0.0.1` is only half the change; the other half is
  every outbound reference that tells a peer "here's where to reach
  me". In deckd that second half lived in `register_sign`'s callback
  URL; in a different system it might be a service-discovery
  registration, a config file emitted to another process, or a DNS
  record. Whenever a bind address changes, search for every
  `:{listen_port}` and every old address literal in the same diff.

### Process

- **A plan with this much surgical specificity (exact files, exact
  diffs, exact test names) is a strictly-better input than an informal
  task list, even for "simple" Level 2 rework.** Every step had a one-
  line test for "did I do it?" which meant zero ambiguity during build.
  Caveat below about what surgical specificity *doesn't* buy you.
- **Preflight paid for itself here** — not by catching a plan defect
  (there didn't seem to be any), but by pre-verifying the half-dozen
  codebase-touchpoint assumptions (`call_subscribe` follows dbus-next's
  lower-snake-case convention; `try_*` callers are already `async`;
  `OnAirButton` has exactly one call site; etc.) that would otherwise
  have been discovered during build as mid-flight surprises.
- **Surgical specificity is a local property; it doesn't find the
  adjacent-step gap.** The plan's step 5 ("bind to `127.0.0.1`") and
  the pre-existing `register_loop` ("advertise `guess_primary_ipv4()`
  as the callback URL") were each internally consistent with their own
  framing. The bug sat between them, and neither preflight nor QA is
  structured to ask "what else in the codebase still references the
  thing this step changed?" Process patch for future address/URL/ID
  changes: add a "callers / consumers / advertised references" grep
  to the plan step itself, with evidence (command + grep output) in
  the plan doc. Would have taken 30 seconds; would have caught this.
- **Test planning has a similar blind spot.** Every planned test
  verified a behavior the plan explicitly named. None of the tests
  asked "what behavior that *isn't* in the plan does this change
  affect?" A single "OnAir register-and-callback round-trip" test
  using the Flask test client against the bound address would have
  exercised the very path that broke on hardware. For future rework
  that changes I/O boundaries, add at least one end-to-end test
  across the boundary, not just unit tests of the changed functions.

### Million-Dollar Question

If the "every blocking I/O call bounces off the event loop via
`asyncio.to_thread`, every HID-thread callback bounces back to the
loop via `asyncio.run_coroutine_threadsafe` with a logging done-
callback" invariant had been a foundational assumption from day one,
the original build would have landed both buttons with the scheduled-
dispatch shape up-front, and the three `systemctl_*` helpers would
have been `async def` from their first line. The rework PR would not
have existed. The lesson for future daemons that mix asyncio + HID
callback threads + blocking HTTP: write the thread-safety invariant
into `systemPatterns.md` **before** the first button, not after PR
review.

The rework also makes `systemPatterns.md`'s concurrency paragraph
authoritative — future buttons should now read it first and will get
this shape for free.
