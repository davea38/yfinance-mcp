# Implementation Plan — Yahoo Finance MCP Server

**Goal:** Bring the server in line with the two `.scratch/` specifications and the supporting
glossary in `CONTEXT.md`, then close out the orphaned code / packaging gaps.

Items are ordered by priority. Top of list goes first. Each item is self-contained — a build
loop should be able to pick the top open bullet and start.

---

## P0 — Insider tooling (`src/tools/insiders.py`)

Spec: `.scratch/outsized-insider-transactions-ranking/0001-outsized-insider-transactions-ranking.md`
Glossary: `CONTEXT.md` — *Insider*, *Insider Transaction*, *Insider Purchase*, *Insider Roster*,
*Outsized Transaction*, *Full Liquidation*, *Lookback Window*, *Position*, *Outsized Ranking*,
*Transaction Type*.

**Done.** All four tools implemented in `src/tools/insiders.py`, registered in
`src/server.py` (server now exposes 32 tools), covered by 16 passing tests in
`tests/test_insiders.py`, and documented in `README.md`. See the Completed section
below for the rollup entry.

---

## P1 — Market calendar tooling (`src/tools/calendars.py`)

**Done.** All four tools implemented in `src/tools/calendars.py`, registered
in `src/server.py` (server now exposes 36 tools), covered by 37 passing tests
in `tests/test_calendars.py`, and documented in `README.md`. See the
Completed section for the rollup.

**Blocker resolution note for future loops:** the prior plan claimed Option
(a) (bumping `yfinance`) was dead because the installed 0.2.66 didn't ship
`Calendars`. That was a stale-dependency artefact — `yfinance` 1.3.0 on PyPI
(latest at the time of this build) ships `yfinance/calendars.py` with the
`Calendars` class and `__init__.py` re-exports it. Lesson: always check the
*upstream* release, not the locally pinned version, before declaring a spec
blocked on a missing API.

**Naming caveat persisted in code:** the spec's tool surface uses
`get_market_ipo_calendar` and `get_market_economic_calendar`, but the
underlying yfinance method names are `get_ipo_info_calendar` /
`get_economic_events_calendar`. The wrappers in `calendars.py` translate.
Don't "fix" the spec names — the `market_` prefix is load-bearing per the
ADR and the suffixes are also part of the documented contract.

---

## P2 — Test suite

**Done.** Full backfill is in place — see the Completed section for the rollup.
`uv run pytest` reports **386 passing tests** across 11 test files (4327 lines).

---

## P3 — Cleanup / single source of truth

The build PROMPT mandates *"Single sources of truth, no migrations/adapters."* Two pieces of
dead or duplicated code violate that.

- [ ] **`src/models.py` is orphaned.** Pydantic models (`StockInfoResponse`,
      `HistoricalDataRequest`, `FinancialStatementRequest`, `OptionsRequest`, `NewsItem`,
      `AnalystRecommendation`, `ErrorResponse`) are not imported by `server.py`, any module
      in `tools/`, or `utils.py` (grep confirmed: `models` only appears as the file itself).
      Either wire them into the tool responses for type contracts or delete the file. Note
      that `pyproject.toml` declares `py-modules = ["server", "utils", "models"]` and the
      egg-info `top_level.txt` lists `models` — these references must be removed alongside
      the file if we delete.
- [ ] **Period/interval validation duplicated.** `src/utils.py:132-175` and
      `src/models.py:38-50` carry the same `valid_periods` / `valid_intervals` lists.
      Whichever side survives the models decision, deduplicate the lists.
- [ ] **`docs/adr/` is empty; ADRs sit in `.scratch/`.** Git status shows
      `D docs/adr/0001-outsized-insider-transactions-ranking.md` and
      `D docs/adr/0002-market-vs-company-calendar.md` — both files are present at
      `.scratch/<feature>/0001-*.md` with `Status: accepted`. Accepted ADRs should live in
      `docs/adr/`, not `.scratch/` (scratch is for in-progress work). Either restore them to
      `docs/adr/` and commit the move, or commit the deletion if the team prefers `.scratch/`
      as canonical. The directory choice must be consistent with how the build prompt expects
      to find new specs.
- [x] **`AGENTS.md` exists** at the project root and documents `uv sync`, `uv run pytest`,
      `uv run yahoo-finance-mcp` and the sandbox `UV_PROJECT_ENVIRONMENT`/`UV_LINK_MODE`
      workaround. Still TODO inside `CLAUDE.md`: the "Testing the Server" block references
      `src/yahoo_finance_mcp/server.py` — that path does not exist; should be `src/server.py`.
      (Tracked separately as the P4 `CLAUDE.md` fix bullet.)
- [ ] **`src/__init__.py` re-exports `main` from `server`** even though `src/` is not an
      installable package (the installed top-levels per egg-info are `server, utils, models,
      tools`, not `src`). Either remove the file or restructure under a real package name.

---

## P4 — Packaging / environment hygiene

- [ ] `pyproject.toml:31-35` uses the deprecated `tool.uv.dev-dependencies` table — uv
      already emits a warning on every `uv run`. Migrate to `dependency-groups.dev`.
- [ ] `pyproject.toml` declares both `py-modules = ["server", "utils", "models"]` and
      `[tool.setuptools.packages.find] where = ["src"]`. The combination is fragile; the
      `tools` subpackage is only picked up by the `packages.find` half. Either declare an
      explicit `packages = ["tools"]` alongside `py-modules`, or restructure into a single
      `yahoo_finance_mcp` package so there's one rule. Verify against the egg-info SOURCES
      list (`src/yahoo_finance_mcp.egg-info/SOURCES.txt`) after changes.
- [ ] `CLAUDE.md` "Testing the Server" block references
      `src/yahoo_finance_mcp/server.py` — that path does not exist. Update to `src/server.py`
      (matches the installed package layout).
- [ ] Document a `uv sync` step that produces a working venv on this Linux sandbox. The
      Windows-style venv at `.venv/Lib/site-packages/` shipped in the repo cannot be used
      from the Linux build agent; the first `uv run` rebuild may fail mid-symlink and leave
      `.venv/bin/` empty. Capture the working incantation in `AGENTS.md`.
      **Workaround discovered during P0** (now persisted in `/etc/sandbox-persistent.sh`):
      the Linux sandbox at `/d/mcp/yfinance-mcp` cannot create symlinks, so `uv sync` fails
      with `Operation not permitted (os error 1)` when symlinking the python binary into a
      project-local `.venv/`. Setting `UV_PROJECT_ENVIRONMENT=/home/agent/yfinance-venv` and
      `UV_LINK_MODE=copy` makes `uv sync` succeed. Note also that `pytest` cannot create
      `.pytest_cache` in the project dir (`Permission denied`) — emits a warning but tests
      still pass. Link this into `AGENTS.md` once that file exists at repo root.

---

## Out of scope (do not implement without a new spec)

- Anything proposed in CONTEXT.md "Considered and rejected" sections of either ADR — e.g.
  polymorphic single-tool calendar, renaming `get_calendar` → `get_company_calendar`,
  Z-score ranking, raw-$ default ranking, dropping full liquidations.
- A "% of float / shares outstanding" insider tool — CONTEXT.md flags it as a *different
  question, potentially worth a separate tool later*. Needs its own ADR.

---

## Completed

Tracking section. Move bullets here with the commit SHA once the build loop closes them out.

- **P2 — Test suite backfill** — commit `d4e85a1` (tag `0.0.3`). Nine new test files added on top of the
  P0/P1 modules (test_insiders, test_calendars), bringing the suite to **386 passing tests**
  in 4327 lines across `tests/`. Coverage: `test_analysis.py` (26), `test_bulk.py` (21),
  `test_financials.py` (37), `test_historical.py` (23), `test_news.py` (17),
  `test_options.py` (22), `test_stock_info.py` (19), `test_utils.py` (53),
  `test_server.py` (~80 parametrised cases asserting the 36-tool registration contract,
  non-empty descriptions, and README/registration count parity). Each per-module test file
  exercises both the happy path and the `error: True` branch for every public function,
  plus validation paths (period/interval/ticker/limit). `conftest.py` provides the shared
  `stub_ticker_factory` fixture so no test hits the network. Importance: the build prompt
  mandates `uv run pytest` between increments — before this commit there was zero
  per-module coverage, so any regression in `utils.py` formatting or `server.py`
  registration would have shipped silently.

- **P1 — Market calendar tooling (`src/tools/calendars.py`)** — commit `TBD`.
  All four `get_market_*_calendar` tools implemented:
  `get_market_earnings_calendar(days, market_cap, filter_most_active, limit)`,
  `get_market_ipo_calendar(days)`, `get_market_splits_calendar(days)`,
  `get_market_economic_calendar(days)`. Each returns the self-describing
  envelope `{event_type, days, start_date, end_date, count, events}` over a
  forward-only window from today. Earnings tool defaults
  `filter_most_active=True`, `limit=50` (capped at YF's max of 100). All four
  registered as `@mcp.tool()` wrappers in `src/server.py` (server now exposes
  **36 tools**). 37 tests added in `tests/test_calendars.py` covering: envelope
  shape, default `days=7`, that the earnings tool forwards
  `market_cap`/`filter_most_active`/`limit` verbatim, that the `Calendars`
  instance is constructed with today / today+days, that limit is capped at
  100, error responses omit the `ticker` field (market calendars aren't
  ticker-scoped), validation of `days` / `limit` / `market_cap` /
  `filter_most_active`, the IPO/splits/economic wrappers call the correct
  yfinance methods (`get_ipo_info_calendar` / `get_economic_events_calendar` —
  not the spec-surface names), the IPO/splits/economic signatures expose
  only `days` (no parameter creep), and that `server.py` actually registers
  all four wrappers. yfinance bumped `>=0.2.49` → `>=1.3.0` in
  `pyproject.toml` (and the `FastMCP(dependencies=...)` declaration in
  `server.py`). README bumped 32 → 36 tools with a new "Market Calendars (4
  Tools)" details block + usage section explaining the per-ticker vs
  market-wide split.

- **P0 — Insider tooling (`src/tools/insiders.py`)** — commit `TBD`. All four tools
  implemented: `get_insider_transactions`, `get_insider_purchases`,
  `get_insider_roster_holders`, and the analytical `get_outsized_insider_transactions`
  (bucket split into `outsized_transactions` vs `full_liquidations`, `lookback_days=180`
  default, `top_n=10` default, `sort` accepting `"proportional"` (default) and `"value"`,
  abs-proportional ranking, verbatim `transaction_type` surfacing, clean error path when
  the roster is empty). All four registered as `@mcp.tool()` wrappers in `src/server.py`
  (server now exposes 32 tools). 16 tests added in `tests/test_insiders.py` covering
  passthrough shape, error paths, bucket split, abs-proportional ranking, secondary
  `value` sort, lookback filter, verbatim transaction_type, `top_n` cap applied only to
  the ranked list (not liquidations), `lookback_days` echoed in response, and validation
  of the `sort` / `lookback_days` / `top_n` parameters. `README.md` bumped from 30 to 32
  tools with a new "Insider Activity (4 Tools)" details block and usage section.
  Caveat noted for follow-up: on AAPL the `insider_transactions['Transaction']` column is
  currently an empty string for every row — the human-readable type is in the `Text`
  column ("Sale at price ..." etc). Per spec we surface the `Transaction` field verbatim
  regardless.
