# AGENTS.md — Operational Notes

Short, command-level cheatsheet for the build/test loop. Status, progress, and
backlog live in `IMPLEMENTATION_PLAN.md`.

## Environment setup (Linux sandbox)

This repo's `/d/mcp/yfinance-mcp` directory does **not** support creating
symlinks, so `uv sync` fails with `Operation not permitted` if it tries to
place a `.venv/` inside the project. Workarounds (already persisted in
`/etc/sandbox-persistent.sh`):

```bash
export UV_PROJECT_ENVIRONMENT=/home/agent/yfinance-venv
export UV_LINK_MODE=copy
```

Run `uv sync` from the project root after setting those.

## Commands

```bash
# Install / refresh deps
uv sync

# Run the full test suite
uv run pytest

# Run a single tests file
uv run pytest tests/test_insiders.py -v

# Run the MCP server (stdio mode)
uv run yahoo-finance-mcp

# Run the MCP server over HTTP for the inspector
uv run yahoo-finance-mcp --http --port 8080
```

`pytest` emits a `PytestCacheWarning` because the sandbox can't create
`.pytest_cache/` under the project; tests still pass. Safe to ignore.

## Source layout reminders

* Tool modules live at `src/tools/<feature>.py` and import utilities with
  `from utils import ...` (the `src/` directory is the import root).
* Wrappers register in `src/server.py` with `@mcp.tool()`; keep their
  docstrings one-line and LLM-facing.
* `src/yahoo_finance_mcp/` does **not** exist. CLAUDE.md's `mcp dev` command
  pointing to that path is stale — the actual entry is `src/server.py`.
