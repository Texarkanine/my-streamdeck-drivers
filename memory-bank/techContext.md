# Tech Context

Python daemon packaged with **`uv`** and **`pyproject.toml`** (committed
**`uv.lock`**). Python floor is pinned in `pyproject.toml` (`requires-python`)
and `.python-version`; the target host runs Ubuntu 22.04 system Python.
Dependencies and entry points are declared in `pyproject.toml`; see it for
the current set (currently: `streamdeck`, `requests`, `dbus-next`, `flask`,
`tomli`, `pillow`; dev extras: `pytest`, `pytest-asyncio`).

## Environment Setup

- Install **`uv`** per [Astral docs](https://docs.astral.sh/uv/).
- Use **`uv sync`** to install from the lockfile; **`uv run`** to execute
  the app without manual venv activation.
- Python version pinned in **`.python-version`** (and floor in
  `pyproject.toml`).

## Build Tools

- **`pyproject.toml`** — project metadata, dependencies, entry point
  (`deckd` console script), hatchling build config.
- **`uv.lock`** — locked versions. Regenerate with **`uv lock`** when
  dependencies change.
- **`[tool.uv] index-strategy = "unsafe-best-match"`** — set because
  environments with extra indexes (e.g. PyTorch wheels) can otherwise
  shadow PyPI and pin stale transitive packages.

## Testing Process

- Tests run under **`pytest`** as configured in `pyproject.toml`
  (`[tool.pytest.ini_options]`); invoke with **`uv run pytest`**.
- `asyncio_mode = "auto"` is set so async test functions don't need
  per-test decorators.
- Hardware/OS-dependent paths (StreamDeck USB, D-Bus) are **mocked** in
  tests; real-hardware validation happens only on the operator's target
  host, not in CI.

## Design System

- No dynamic text rendering on keys: state is shown via **PNG assets**
  in a configurable directory. Required filenames and the 80×80 Mini
  size are documented in `images/README.md`.
