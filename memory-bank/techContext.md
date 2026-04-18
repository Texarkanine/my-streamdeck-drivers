# Tech Context

Python daemon targeting **Python 3.11+**, packaged with **`uv`**, **`pyproject.toml`**, and a committed **`uv.lock`**. Primary libraries (see `VISION.md` / future `pyproject.toml`): `streamdeck`, `requests`, D-Bus (`dbus-next` or similar), and a small HTTP stack for the OnAir sign (likely Flask for parity with existing sign code).

## Environment Setup

- Install **`uv`** per [Astral docs](https://docs.astral.sh/uv/).
- Use **`uv sync`** to install from the lockfile; **`uv run`** to execute the app without manual venv activation.
- Python version pin via **`.python-version`** for local and CI consistency.

## Build Tools

- **`pyproject.toml`** — project metadata, dependencies, entry points; **`uv.lock`** — locked versions. Regenerate with **`uv lock`** when dependencies change.
- **`[tool.uv] index-strategy`** — if the environment adds extra package indexes that shadow PyPI, `unsafe-best-match` lets resolution pick compatible versions from PyPI when needed.

## Testing Process

- To be defined as the codebase lands; workspace rules emphasize TDD where applicable. Commands will live in `pyproject.toml` or CI config once added.

## Design System

- No dynamic text rendering on keys: state is shown via **PNG assets** in a configurable directory (documented filenames and dimensions).
