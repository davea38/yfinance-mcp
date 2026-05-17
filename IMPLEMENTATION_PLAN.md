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

## P1 — Market calendar tooling (`src/tools/calendars.py`) — **spec blocked**

Spec: `.scratch/market-vs-company-calendar/0001-market-vs-company-calendar.md`
Glossary: `CONTEXT.md` — *Company Calendar* (existing) vs *Market Calendar* (new).

**Blocker — confirmed.** The spec assumes a `yfinance.Calendars` class with
`.get_earnings_calendar(...)`, `.get_ipo_calendar(...)`, `.get_splits_calendar(...)`,
`.get_economic_calendar(...)` methods. Re-verified against the currently installed
**yfinance 0.2.66** (via `dir(yfinance)` during the P0 build): **no `Calendars` symbol
and no `*_calendar` method anywhere**. The public exports are `download, Market, Search,
Lookup, Ticker, Tickers, Sector, Industry, WebSocket, AsyncWebSocket, EquityQuery,
FundQuery, screen, …` — none of these surface a market-wide calendar. **Option (a) below
is dead** until/unless a future yfinance release ships `Calendars`; the next loop should
pursue option (b).

Action plan, in order:

- [ ] **Resolve the dependency claim first.** Option (a) — bumping `yfinance>=…` to a release
      that exposes `Calendars` — is **dead as of yfinance 0.2.66** (no such symbol exists
      upstream). The next loop must pursue option (b): either rewrite the spec at
      `.scratch/market-vs-company-calendar/0001-market-vs-company-calendar.md` to reflect a
      revised data source, or implement the four tools via direct HTTP against the public
      `query1.finance.yahoo.com` calendar endpoints inside this module.
- [ ] **If (a):** create `src/tools/calendars.py` with the four `get_market_*_calendar` tools
      per spec — `days: int = 7` forward-only window, self-describing envelope
      `{event_type, days, start_date, end_date, count, events}`. The earnings tool takes the
      extra `market_cap`, `filter_most_active=True`, `limit=50` parameters; the other three
      take only `days`. Register each in `server.py` with `get_market_*` names — the
      `market_` prefix is load-bearing per the ADR ("Considered and rejected: No `market_`
      prefix").
- [ ] **If (b):** update the spec at
      `.scratch/market-vs-company-calendar/0001-market-vs-company-calendar.md` to reflect the
      revised data source (direct HTTP, or a different upstream library) and re-decide the
      tool surface. Use an Opus subagent with ultrathink as the build prompt directs.
- [ ] Either way, do **not** rename or alter `get_calendar(ticker)` in `analysis.py` — the
      ADR explicitly rejects renaming it to `get_company_calendar` to avoid a breaking
      change for existing clients.
- [ ] Tests in `tests/test_calendars.py` once the source is settled.
- [ ] README update under a new "Market Calendars" section.

---

## P2 — Test suite

`tests/` contains only an empty `__init__.py`. There is zero coverage of any tool, util, or
the server wiring. Build PROMPT requires test runs after each increment.

- [x] Add `tests/conftest.py` with shared fixtures — a `stub_ticker_factory` fixture is in
      place that patches `yfinance.Ticker` per-module so tests don't hit the network.
- [x] One `tests/test_<module>.py` per existing tool module covering the happy path and the
      `error: True` branch — **`tests/test_insiders.py` DONE (16 tests)**. Still pending for
      the rest: `calendars` (blocked on P1), then back-fill `stock_info`, `historical`,
      `financials`, `analysis`, `options`, `news`, `bulk`.
- [ ] `tests/test_utils.py` — `format_dataframe_to_dict` (NaN, Timestamps, numpy scalars),
      `format_series_to_dict`, `validate_ticker_symbol`, `validate_period`,
      `validate_interval`, `handle_yfinance_error` shape.
- [ ] `tests/test_server.py` — assert every registered `@mcp.tool()` name from the spec is
      present, descriptions are non-empty, and that the README tool count (now **32** after
      P0) matches the registration count post-feature work.
- [ ] Wire `uv run pytest` into the build-loop tag step (PROMPT_build.md item 9999999).

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
- [ ] **`AGENTS.md` does not exist** at the project root. PROMPT_build.md item 9999999999
      tells the build loop to update it for "how to run the application". Create the file as
      a stub on first build pass with: `uv sync`, `uv run yahoo-finance-mcp`, `uv run pytest`,
      `uv run mcp dev src/yahoo_finance_mcp/server.py` (note this last command from
      `CLAUDE.md` points to a `yahoo_finance_mcp/` path that does not exist — the actual
      module lives at `src/server.py`; fix the path in `CLAUDE.md` while you're there).
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
