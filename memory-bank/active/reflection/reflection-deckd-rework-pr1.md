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
change to the happy path.

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

Build was a clean walk down the plan; each step was independently
testable and red-green'd without surprises. QA caught exactly one
stylistic nit (`_log_exc(f: Any)` vs the sibling's `f: asyncio.Future[Any]`)
which is exactly the kind of low-cost consistency find that belongs
in the post-build semantic review, not in code review later.

Preflight's advisory call — "keep the `run_coroutine_threadsafe +
done-callback` pattern inlined across two buttons instead of
extracting a helper" — was the right call on a rework PR. The five
lines of boilerplate mirror exactly between `P2PoolButton.on_press`
and `OnAirButton.on_press`; a shared `schedule_and_log` helper would
trade one grep-friendly idiom for one level of indirection. Revisit if
a third caller ever shows up.

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

### Process

- **A plan with this much surgical specificity (exact files, exact
  diffs, exact test names) is a strictly-better input than an informal
  task list, even for "simple" Level 2 rework.** Every step had a one-
  line test for "did I do it?" which meant zero ambiguity during build
  and no QA findings beyond one type-annotation nit. Worth continuing
  to write plans at this granularity for rework tasks even when the
  scope feels small — the cost of detailed planning is always less
  than the cost of one botched rework iteration.
- **Preflight paid for itself here** — not by catching a plan defect
  (there weren't any), but by pre-verifying the half-dozen codebase-
  touchpoint assumptions (`call_subscribe` follows dbus-next's
  lower-snake-case convention; `try_*` callers are already `async`;
  `OnAirButton` has exactly one call site; etc.) that would otherwise
  have been discovered during build as mid-flight surprises.

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
