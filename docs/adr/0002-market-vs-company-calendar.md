# Market Calendar exposed as four tools, separate from Company Calendar

**Status:** accepted

## Context

`yfinance` ships two unrelated APIs that both use the word "calendar":

- `Ticker.calendar` — one company's upcoming earnings + dividend dates. Already exposed
  here as `get_calendar(ticker)` in `analysis.py`.
- `yfinance.Calendars` (plural) — a market-wide stream of four disjoint event types
  (earnings, IPOs, splits, economic events) over a forward date window.

Adding market-wide calendar tools required deciding (a) whether to surface them as one
tool or many, (b) how to name them so an LLM doesn't confuse them with the existing
per-ticker tool, and (c) whether to collapse the two concepts.

## Decision

Four new tools in `tools/calendars.py`, each prefixed `get_market_*`:
`get_market_earnings_calendar`, `get_market_ipo_calendar`, `get_market_splits_calendar`,
`get_market_economic_calendar`. Single `days: int = 7` forward-only window param. The
earnings tool also exposes `market_cap`, `filter_most_active=True`, `limit=50` to avoid
context-bombing the LLM during earnings season. Responses use a self-describing envelope
(`event_type`, `days`, `start_date`, `end_date`, `count`, `events`).

The existing `get_calendar(ticker)` is left untouched.

## Considered and rejected

- **One polymorphic tool with `event_type` enum** — return schemas differ across the
  four streams; LLMs handle polymorphic responses poorly.
- **One tool returning all four buckets in one call** — uncontrolled payload size.
- **No `market_` prefix** — too easily confused with the per-ticker `get_calendar` and
  with per-ticker `get_earnings_dates`, defeating the disambiguation work in CONTEXT.md.
- **Rename `get_calendar` to `get_company_calendar`** — breaking change for existing
  clients for marginal clarity gain; the `market_` prefix on the new tools is enough
  to telegraph the scope split.
- **Collapse the two concepts into one** — they answer different questions
  (per-ticker drill-down vs market-wide scan) and take different inputs; merging would
  produce an awkward `Optional[ticker]` API.

## Consequences

Tool count grows by four. Glossary in CONTEXT.md now formally distinguishes
**Company Calendar** from **Market Calendar**; future tools touching either concept
must respect that split. If `yfinance.Calendars.get_splits_calendar()` turns out not
to support the same filters as `get_earnings_calendar()`, the splits tool will have
a narrower parameter list than its sibling — acceptable, since the four tools are
already a family of variants rather than a uniform interface.
