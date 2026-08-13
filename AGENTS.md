# AGENTS.md

## Project

Single-file Python CLI: `holospec.py`, packaged as `holospec`, Python
>=3.11, dependency-managed with `uv`.

## Bootstrapping HoloSpec if the skill isn't installed yet

If the `holospec` skill isn't installed and no `holospec/`/`openspec/`
directory exists at the project root, don't guess at the workflow:

1. `pip install holospec` (or `uv add holospec` / `uv sync` if this repo
   already depends on it)
2. `holospec init` — detects or scaffolds a project root and installs the
   `holospec` skill file so future turns pick up the full protocol
   automatically.

Once installed, follow the skill's instructions instead of this file.

## Commit messages

Single-line commit messages only. No multiline body, no Co-Authored-By
trailer.

## Contributing to HoloSpec itself

- Install deps: `uv sync` (add `--group e2e` only if working on
  `tests/e2e/`, see cost warning below)
- Run tests: `uv run pytest` (excludes `e2e` by default; enforces 100%
  coverage on `holospec.py`)
- Lint: `uv run ruff check .` (add `--fix` to auto-fix)
- Type check: `uv run mypy holospec.py`

### e2e tests cost money - never run them automatically

`tests/e2e/` drives a real Claude agent (via `claude-agent-sdk`) through the
full OpenSpec-style workflow. Every run makes live API calls and has a real
dollar cost.

- These tests are marked `e2e` and excluded from the default `pytest` run
  (see `-m "not e2e"` in `pyproject.toml`).
- Do not run `pytest -m e2e` or anything under `tests/e2e/` unless the user
  explicitly asks for it in the current request. Do not add e2e runs to CI,
  pre-commit hooks, or any other automatic trigger.
- Install the extra dependencies first: `uv sync --group e2e`.
- Run e2e tests with `--no-cov` (they don't exercise `holospec.py`, so the
  project's `--cov-fail-under=100` would otherwise fail spuriously):
  `uv run pytest -m e2e tests/e2e -v -s --no-cov`.
