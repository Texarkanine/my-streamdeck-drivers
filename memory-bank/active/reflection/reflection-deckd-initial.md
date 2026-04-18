---
task_id: deckd-initial
date: 2026-04-18
complexity_level: 3
---

# Reflection: Implement deckd (VISION + systemd)

## Summary

Shipped a greenfield headless `deckd` Python daemon — Stream Deck Mini with a
P2Pool (systemd D-Bus) button and an OnAir (HTTP sign) button, `uv`-locked,
with install artifacts for systemd/udev/polkit. Operator confirmed it runs on
the target server (`kinglear`); 16/16 tests pass.

## Requirements vs Outcome

All six requirements from `projectbrief.md` were delivered:

1. Package implements the VISION architecture (buttons, config, D-Bus,
   HTTP sign, deck wiring). ✔
2. `pyproject.toml` + committed `uv.lock`. ✔
3. Example `deckd.toml`, systemd unit, udev rules (`0fd9:0063`). ✔
4. README install flow documented. ✔
5. `Restart=always`, `WantedBy=multi-user.target`. ✔
6. Works on Python 3.10.12 / Ubuntu 22.04. ✔

**Scope additions that were not in the plan** (emerged from operator
deployment on real hardware):

- P2Pool "deactivating" state: two-frame blink animation
  (`deactivating_image_a`/`_b`) with a configurable `deactivating_blink_interval_sec`.
- Repeat-press escalation while deactivating: optional
  `deactivating_escalate_signal` (15 / 9) that calls systemd `KillUnit`
  with the chosen signal, so a second press on a stuck unit actually does
  something visible.
- Polkit rules under `install/polkit/` (both the modern `.rules` form and a
  `.pkla` fallback). The plan mentioned a `systemctl` fallback but did not
  call out polkit configuration as a first-class install artifact.

**Scope dropped**: none. One config option mentioned in early docs
(`use_sudo_for_systemctl` + `sudoers-deckd-p2pool.example`) was removed
during a refactor in favor of the polkit-based approach; a stale reference
to it in a polkit rule comment was the only substantive QA finding.

## Plan Accuracy

The plan in `tasks.md` was a good map of the terrain:

- The **component list** (config / http_server / buttons / deck /
  systemd_dbus / `__main__`) matched the final tree almost 1:1. The only
  renames/splits were cosmetic: `systemd_dbus.py` → `systemd_unit.py`,
  `deck.py` → `deck_runtime.py`, and a small `netutil.py` helper that
  wasn't in the plan.
- The **thread/async resolution** ("asyncio main loop for D-Bus + OnAir
  periodic register; Flask in daemon thread; StreamDeck `run()` in daemon
  thread; cross-thread via `asyncio.run_coroutine_threadsafe`") held up
  verbatim through build. That Open Question was worth resolving before
  code — it touched every module.
- The **TDD test plan** landed close to what was written: `test_config.py`,
  `test_http_server.py`, `test_onair_client.py`, `test_p2pool_button.py`,
  `test_p2pool_press_kind.py` — 16 tests, all with mocks, no hardware.
- The **challenges** ("no hardware in CI", "D-Bus on CI") were real but
  well-mitigated by the mock-boundary design.

**What the plan missed**: every single one of the post-build iterations
(blink animation, signal escalation, polkit artifacts) came from *running
the thing on real hardware against a real systemd unit that doesn't stop
cleanly*. No amount of desk-planning would have surfaced "p2pool sometimes
sits in `deactivating` for minutes and the operator wants to hit the
button harder". Planning reached its useful floor at the boundary of
observable-on-hardware behavior.

## Creative Phase Review

No creative phase was run. The three Open Questions in `tasks.md`
(thread/async model, Python version floor, D-Bus auth failure) were each
tractable by a single sentence of reasoning in the plan, not by
divergent design exploration. In hindsight this was the right call — no
phase-structure overhead was wasted on decisions that didn't need it.

## Build & QA Observations

**Build went smoothly for the planned scope.** The package shape, the
asyncio+threads concurrency model, the D-Bus fallback chain, and the HTTP
sign contract all fell out of the plan without rework.

**Build iterated non-trivially *after* "complete".** Inspecting `git log`,
the sequence was:

- `f31170d feat: add deckd Stream Deck daemon with systemd and OnAir integration` — the planned build.
- `a706ec7 fix: send JSON-encoded callback URL for OnAir register POST` — real-world OnAir server interaction.
- `6e33187 feat: detect monero deactivating` — real-world observation #1.
- `20a55ea feat: blink two PNGs during p2pool deactivating at configurable interval` — UX response to #1.
- `47e0265 fix(p2pool): deactivating press escalates with KillUnit; never start while deactivating` — safety + UX.
- `8049426 feat: repeated pushes to kill a systemd unit hardre` — operator-driven iteration.

Roughly half the feature surface area landed in this post-build loop.

**QA caught one trivial doc-drift issue only** — a polkit rule comment
that still referenced the pre-reorg install path
(`install/99-deckd-p2pool.rules` → `install/polkit/…`) and a config
option (`use_sudo_for_systemctl`) that had been removed during the
polkit-first refactor. No logic defects; no test failures.

## Cross-Phase Analysis

Two causal chains worth naming:

1. **Refactor-drift in comments.** The install tree was reorganized from
   flat `install/*` into `install/{systemd,udev,polkit}/` during build, and
   the polkit→sudoers design was swapped for polkit-only. The code was
   updated cleanly; the *comment at the top of the polkit rule* was not.
   QA caught it. The causal chain is simple: refactors that move files and
   remove config keys need a grep for the old names/paths across *all*
   file types, not just source. Comments and example-configs are the usual
   stragglers.

2. **Plan-to-reality gap on "deactivating".** The plan modeled P2Pool state
   as a binary `ActiveState` (active / inactive) with `StartUnit` / `StopUnit`
   as the only actions. Real systemd units have an `activating` /
   `deactivating` middle state that can stall, and the plan's binary model
   had no vocabulary for "press during deactivating". This didn't cause a
   build problem per se — the code was correct for the model it was
   given — but it forced a post-build feature loop once hardware runtime
   expanded the model. A more thorough systemd state-machine sketch
   during plan (all six `ActiveState` values, not just two) would likely
   have surfaced this pre-build.

Preflight did its job: it caught nothing dramatic because the plan *was*
rock-solid for the scope it covered. The gaps were in scope-definition,
not plan-quality.

## Insights

### Technical

- **Systemd units can stall in `deactivating`; a button-style UI needs
  both a visual cue and an escalation path.** The pattern that landed
  (`monero_deactivating_{a,b}.png` blink + repeat-press → `KillUnit` with
  configurable signal, never `StartUnit` while deactivating) is reusable
  for any other long-shutdown unit.
- **Polkit unit-name matching is unreliable.** `action.lookup("unit")`
  doesn't consistently return a matchable string across systemd versions,
  so unit-scoped rules can silently fail auth. The documented workaround
  is to allow `org.freedesktop.systemd1.manage-units` for a specific Unix
  user and scope further via group membership or a dedicated service
  account — this is now captured in the `install/polkit/` comment.
- **When modeling systemd state, enumerate all six `ActiveState` values
  up front**, not just `active`/`inactive`. The transition states
  (`activating`, `deactivating`, `failed`, `reloading`) each deserve an
  explicit UX decision, even if that decision is "ignore".
- **Cross-thread asyncio glue via `asyncio.run_coroutine_threadsafe` is
  clean when the main loop is unambiguous.** Pinning the D-Bus subscriber
  and periodic OnAir re-register to the asyncio main, and putting Flask +
  StreamDeck in daemon threads, gave one obvious place to forward every
  callback to. Worth keeping as a template.

### Process

- **Skipping the creative phase was correct for this task.** The open
  questions were narrow enough to answer in plan. Not every Level 3 task
  needs creative; reserve it for tasks with genuinely divergent design
  options.
- **Hardware/OS-integration features have a hard plan-ceiling.** No
  amount of pre-build analysis would have surfaced "operator wants to
  punch the stop button again when the unit is stuck". For this class of
  work, the efficient loop is: plan → minimum viable build → deploy to
  real hardware → iterate on observed behavior. Budget explicitly for the
  post-deploy iteration loop instead of treating it as scope creep.
- **When refactoring file layout or removing config keys during build,
  `rg` for the old names across the full tree (docs, comments, example
  configs, rules files) — not just source.** This would have caught the
  single QA finding pre-QA.
- **Committing scope additions as their own feature commits
  (`feat: detect monero deactivating`, `feat: blink …`,
  `fix(p2pool): deactivating press escalates …`) preserved a clean
  narrative** of what was planned vs what emerged from real-world use.
  Useful later when reading history to understand *why* the code looks
  the way it does.
