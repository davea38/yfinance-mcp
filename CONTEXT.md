# Yahoo Finance MCP — Domain Context

This server exposes Yahoo Finance data via MCP tools for LLM clients. The glossary below captures
terms whose meaning is non-obvious or routinely conflated, especially in the insider-activity area.

## Language

**Company Calendar**:
A *per-ticker* snapshot of one company's upcoming corporate events — next earnings date,
dividend dates, ex-dividend date — sourced from `Ticker.calendar`. Returned by
`get_calendar(ticker)` in `analysis.py`. One ticker in, one company's events out.
_Avoid_: "calendar" unqualified (collides with **Market Calendar**); "earnings calendar"
(too narrow — also includes dividend events).

**Market Calendar**:
A *market-wide* stream of upcoming events sourced from the `yfinance.Calendars` class,
bounded by a forward date window (default next 7 days). Four disjoint streams —
**Earnings**, **IPO**, **Splits**, **Economic Events** — each exposed as its own tool
in `tools/calendars.py`. Returns rows for many tickers (or none, for economic events).
_Avoid_: "calendar" unqualified; "upcoming earnings" (ambiguous re: per-ticker vs market).

**Insider**:
An officer, director, or 10%-plus beneficial owner of a public company — i.e. a person required
to disclose trades to the SEC on Form 4. The `Position` column on a transaction record carries
the specific role (e.g. `CEO`, `Director`, `10% Owner`, `Officer`).
_Avoid_: "shareholder" (too broad), "executive" (excludes directors and 10% owners).

**Insider Transaction**:
A single reported buy or sell event by one **Insider** — a row in a log keyed by date, name,
position, transaction type, share count, and value.
_Avoid_: "insider trade" (ambiguous re: aggregate vs. single).

**Insider Purchase**:
An aggregate *summary* of insider buy/sell activity over a recent window (e.g. net shares,
total buys, total sales, percent change). Not a list of individual trades.
_Avoid_: confusing with **Insider Transaction**; "purchase" here is a summary metric, not one buy.

**Insider Roster**:
A *snapshot* of who currently holds insider shares and how many — accumulated position sizes,
not a transaction log.
_Avoid_: "insider holders" (collides with the holders-trio terminology below).

**Holders trio** (existing, non-insider):
**Major Holders**, **Institutional Holders**, **Mutual Fund Holders** — three separate tools
in `stock_info.py` that report ownership concentration by category. Insider tooling mirrors
their pattern.

## Relationships

- **Company Calendar** and **Market Calendar** are orthogonal: same word, different
  scope axis. A **Company Calendar** answers "what's coming up for *this* ticker?";
  a **Market Calendar** answers "what's happening in *the market* over the next N days?".
  They are not interchangeable and should not be merged.
- An **Insider** produces zero or more **Insider Transactions** over time.
- **Insider Purchase** is a derived summary computed by Yahoo over a recent window of
  **Insider Transactions**.
- **Insider Roster** is orthogonal to **Insider Transactions** — it shows current position
  sizes, not activity.
- The analytical tool combines **Insider Transactions** (numerator) with **Insider Roster**
  (denominator) to surface **Outsized Transactions**, with **Full Liquidations** in a
  separate response bucket when the denominator is missing.
- All four insider tools live in `src/tools/insiders.py`.

## Example dialogue

> **Dev:** "The user asked for insider transactions — can I just expose `insider_transactions`?"
> **Domain expert:** "Three different things hide behind that phrase. **Insider Transactions**
> is the log, **Insider Purchases** is the aggregate summary Yahoo computes, and **Insider Roster**
> is the current-holdings snapshot. They answer different questions; expose all three."

**Outsized Transaction**:
An **Insider Transaction** ranked primarily by `shares_transacted / insider_current_holdings`
(i.e. what fraction of that insider's stake the trade represents). A `$ value` ranking is
offered as a secondary sort. Filterable by **Position** (e.g. limit to `Officer` and
`Director`, excluding `10% Owner`).
_Avoid_: "big trade" (ambiguous re: dollar vs. share vs. proportional).

**Full Liquidation**:
An **Insider Transaction** whose actor has zero current holdings (absent from
**Insider Roster**) — the ratio denominator is undefined. Categorically distinct from a
trimmed position and surfaced in its own response bucket, not mixed into the ranked list.

**Lookback Window**:
The trailing time window of **Insider Transactions** the analytical tool considers when
ranking. Default 180 days, overridable per call via `lookback_days`. The three passthrough
tools (transactions / purchases / roster) do not expose this parameter — they return
whatever Yahoo provides unfiltered.

**Position**:
The role string (e.g. `CEO`, `Director`, `Officer Director`, `10% Owner`,
`Beneficial Owner (10%)`) attached to each **Insider Transaction**. Surfaced verbatim on
every row in the analytical tool's output so the LLM can judge signal quality per role —
not used as a filter dimension. Yahoo does not normalize this field, so consumers should
expect free-form variants rather than a clean enum.

**Outsized Ranking**:
The order of the `outsized_transactions` bucket — sorted by `abs(holdings_pct_change)`
descending, so a large buy and a large sale of equal proportional size are surfaced
equally. Direction is read off **Transaction Type**, not the sort key. Default depth is 10
rows (parameter `top_n`); `full_liquidations` is uncapped within the window.

**Transaction Type**:
The verbatim Yahoo transaction descriptor (e.g. `Sale`, `Sale - market`, `Purchase`,
`Stock Award`, `Gift`, `Option Exercise`). Surfaced as-is — `Stock Award` and
`Option Exercise` mechanically inflate `holdings_pct_change` without being market
signals (the insider didn't choose to buy), but we do not pre-filter; the LLM weighs
them via this field.

## Flagged ambiguities

- "calendar" colloquially overloads two scopes — resolved as **Company Calendar**
  (per-ticker) vs **Market Calendar** (market-wide). Tool names use the `market_` prefix
  to telegraph the scope to LLM clients.
- "insider transactions" colloquially covers all three insider endpoints — resolved by the
  three distinct terms above.
- "outsized" — resolved as a proportional measure (% of insider's holdings), not raw dollars
  or shares. The lazy "biggest $ trade" view is available as a sort option but not the default
  because absolute size disguises the strength of a signal: a small trade that liquidates a
  position is louder than a large trade that trims one.
