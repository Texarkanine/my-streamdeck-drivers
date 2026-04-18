# Active Context

**Current Task:** deckd-rework-pr1 — PR-feedback hardening rework on `deckd-initial`

**Phase:** PREFLIGHT - PASS (with advisory)

**What Was Done:** Validated the 11-step plan against the codebase. Verified (a) `OnAirButton` constructor change only touches `__main__.py` call site and matches the existing `P2PoolButton(*, loop=…)` convention; (b) sync `systemctl_{kill,start,stop}` has no callers outside `try_{kill_unit,start_stop}` inside `systemd_unit.py`, and the two `try_*` helpers are already `async` with callers in `p2pool.py` already using `await`; (c) `call_subscribe()` follows dbus-next's CamelCase→`call_<snake_case>` convention used elsewhere (`call_start_unit`, `call_kill_unit`); (d) docs sweep targets are accurate (README step 4 still says "reachable from the OnAir server"; `systemPatterns.md` concurrency section is the right home for the new sentence). No conflicts, no missing touchpoints.

**Advisory (not blocking):** the `run_coroutine_threadsafe + done-callback logger` pattern will now live in two buttons. A `deckd/asyncutil.py::schedule_and_log(coro, loop, desc)` helper would DRY it, but two call sites is a thin justification on a rework PR; keeping the pattern inlined preserves review surgery.

**Next Step:** Build (`niko-build` skill) — start with TDD step 1 (OnAirButton `loop` parameter).
