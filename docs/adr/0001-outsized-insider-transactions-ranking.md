# Outsized Insider Transactions: ranking and bucket structure

**Status:** accepted (2026-05-17)

The `get_outsized_insider_transactions` MCP tool ranks insider trades primarily by
`shares_transacted / insider_current_holdings` (the proportional share of the insider's
stake the trade represents), not by raw dollar value. When the denominator is missing —
i.e. the insider is no longer on `insider_roster_holders` because they fully exited —
those rows are surfaced in a separate `full_liquidations` response bucket rather than
mixed into the ranked list or silently dropped.

## Considered Options

- **Rank by dollar value.** Simplest, but disguises signal strength: a $10M sale by an
  insider holding $500M tells you less than a $1M sale that clears 90% of someone's stake.
- **Rank by share count.** Even weaker — ignores both price and position size.
- **Rank by Z-score against the insider's own history.** Statistically principled but
  brittle: most insiders have 3-5 lifetime trades, so the Z-score is mostly noise.
- **Rank by % of float / shares outstanding.** Measures materiality to the company, not
  to the actor. Different question; potentially worth a separate tool later.
- **Mix full liquidations into the main list with `ratio: null`.** Forces consumers to
  handle nulls and special-case sort logic. The bucket split keeps the response shape
  clean and signals that a full exit is categorically different from a trim.
- **Drop full liquidations as un-rankable.** Rejected outright — full exits are the
  loudest possible signal; silently hiding them would defeat the tool's purpose.

## Consequences

- Two yfinance calls per invocation (`insider_transactions` + `insider_roster_holders`),
  not one. Tickers with no roster data return a clean error directing the LLM to
  `get_insider_transactions` for the raw log.
- `Stock Award` and `Option Exercise` rows mechanically inflate the ratio without being
  market signals. We surface the verbatim `transaction_type` rather than pre-filtering;
  consumers (LLMs) judge weight per row.
- The default 180-day `lookback_days` is encoded in the contract; widening it later is
  fine, but tightening it would be a breaking change for callers depending on the
  current window.
