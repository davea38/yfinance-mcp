"""Insider activity tools for Yahoo Finance MCP server.

Four tools live in this module:

* ``get_insider_transactions`` — pass-through of ``Ticker.insider_transactions``;
  the raw per-trade log Yahoo publishes for each ticker.
* ``get_insider_purchases`` — pass-through of ``Ticker.insider_purchases``; the
  *aggregate* summary (purchases vs. sales) Yahoo computes, not a list of trades.
* ``get_insider_roster_holders`` — pass-through of ``Ticker.insider_roster_holders``;
  a snapshot of who currently holds insider shares and how many.
* ``get_outsized_insider_transactions`` — analytical tool that joins the
  transactions log to the roster on insider name and ranks rows by
  ``shares_transacted / insider_current_holdings`` (proportional impact on the
  insider's own stake). Rows whose actor is absent from the roster (i.e. they
  fully exited the position) are surfaced in a separate ``full_liquidations``
  bucket rather than mixed into the ranked list — see the ADR at
  ``.scratch/outsized-insider-transactions-ranking/0001-outsized-insider-transactions-ranking.md``
  for the reasoning.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pandas as pd
import yfinance as yf

from utils import (
    format_dataframe_to_dict,
    handle_yfinance_error,
    validate_ticker_symbol,
)


_VALID_SORTS = ("proportional", "value")


def get_insider_transactions(ticker: str) -> Dict[str, Any]:
    """Return the raw insider-transactions log for a ticker.

    Pass-through of ``yfinance.Ticker.insider_transactions``. One row per
    reported buy/sell with insider name, role, share count, dollar value,
    transaction descriptor and ownership flag (D/I). No ``lookback_days``
    parameter — Yahoo returns whatever window it returns; consumers wanting a
    bounded analytical view should use ``get_outsized_insider_transactions``.
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        df = stock.insider_transactions

        if df is None or df.empty:
            return {
                "error": True,
                "message": f"No insider transactions data available for {ticker}",
                "ticker": ticker,
            }

        return {
            "ticker": ticker,
            "insider_transactions": format_dataframe_to_dict(df),
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching insider transactions")


def get_insider_purchases(ticker: str) -> Dict[str, Any]:
    """Return Yahoo's aggregate insider purchases/sales summary.

    Pass-through of ``yfinance.Ticker.insider_purchases``. This is the trailing
    six-month rollup Yahoo computes (purchases, sales, net shares, % change,
    total insider shares held) — *not* a list of individual trades. Use
    ``get_insider_transactions`` for the per-trade log.
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        df = stock.insider_purchases

        if df is None or df.empty:
            return {
                "error": True,
                "message": f"No insider purchases summary available for {ticker}",
                "ticker": ticker,
            }

        return {
            "ticker": ticker,
            "insider_purchases": format_dataframe_to_dict(df),
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching insider purchases summary")


def get_insider_roster_holders(ticker: str) -> Dict[str, Any]:
    """Return the current insider-roster snapshot for a ticker.

    Pass-through of ``yfinance.Ticker.insider_roster_holders``. Each row is one
    current insider with their position, latest-transaction date and shares
    owned directly. Orthogonal to the transactions log — answers "who holds
    what right now", not "what did they do recently".
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        df = stock.insider_roster_holders

        if df is None or df.empty:
            return {
                "error": True,
                "message": f"No insider roster data available for {ticker}",
                "ticker": ticker,
            }

        return {
            "ticker": ticker,
            "insider_roster_holders": format_dataframe_to_dict(df),
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching insider roster")


def _coerce_float(value: Any) -> Any:
    """Best-effort float coercion that tolerates pandas NA/None and stringly numbers."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_name(name: Any) -> str:
    if name is None:
        return ""
    try:
        if pd.isna(name):
            return ""
    except (TypeError, ValueError):
        pass
    return str(name).strip().upper()


def get_outsized_insider_transactions(
    ticker: str,
    lookback_days: int = 180,
    top_n: int = 10,
    sort: str = "proportional",
) -> Dict[str, Any]:
    """Rank recent insider trades by their proportional impact on the insider's own stake.

    Joins ``Ticker.insider_transactions`` (numerator) to
    ``Ticker.insider_roster_holders`` (denominator) on insider name. The
    primary sort key is ``abs(shares_transacted / insider_current_holdings)``
    so a 90% sale and a 90% purchase rank equally; direction is read off the
    verbatim ``transaction_type`` column (``Sale``, ``Purchase``,
    ``Stock Award`` …) which is surfaced as-is, *not* pre-filtered.

    Args:
        ticker: Stock ticker symbol.
        lookback_days: Trailing window (default 180) for the transactions log.
            Part of the contract — widening later is safe, tightening would
            break callers depending on the current window.
        top_n: Cap on the ranked list (default 10). The
            ``full_liquidations`` bucket is uncapped within the window — a full
            exit is the loudest possible signal and must not be silently
            dropped.
        sort: ``"proportional"`` (default) ranks by
            ``shares_transacted / insider_current_holdings``; ``"value"``
            ranks by raw dollar value as the documented secondary sort. Both
            sort by absolute magnitude so buys and sells of equal size rank
            equally.

    Returns:
        ``{"ticker", "lookback_days", "outsized_transactions",
        "full_liquidations"}`` where each row carries ``date``, ``name``,
        ``position``, ``transaction_type``, ``shares_transacted``, ``value``,
        ``insider_current_holdings`` and ``holdings_pct_change``. Rows in
        ``full_liquidations`` have ``insider_current_holdings == 0`` and
        ``holdings_pct_change is None`` — the ratio is undefined because the
        actor is no longer on the roster.

        If ``insider_roster_holders`` is empty an error response directs the
        LLM to ``get_insider_transactions`` for the raw log.
    """
    try:
        ticker = validate_ticker_symbol(ticker)

        if not isinstance(lookback_days, int) or lookback_days <= 0:
            raise ValueError("lookback_days must be a positive integer")
        if not isinstance(top_n, int) or top_n <= 0:
            raise ValueError("top_n must be a positive integer")
        if sort not in _VALID_SORTS:
            raise ValueError(
                f"Invalid sort '{sort}'. Must be one of: {', '.join(_VALID_SORTS)}"
            )

        stock = yf.Ticker(ticker)
        txns = stock.insider_transactions
        roster = stock.insider_roster_holders

        if roster is None or roster.empty:
            return {
                "error": True,
                "message": (
                    f"No insider roster data available for {ticker}; the ratio "
                    "denominator (insider_current_holdings) is missing. Call "
                    "get_insider_transactions for the raw transaction log."
                ),
                "ticker": ticker,
            }

        if txns is None or txns.empty:
            return {
                "ticker": ticker,
                "lookback_days": lookback_days,
                "outsized_transactions": [],
                "full_liquidations": [],
            }

        cutoff = pd.Timestamp(datetime.now(timezone.utc).date()) - pd.Timedelta(
            days=lookback_days
        )
        parsed_dates = pd.to_datetime(txns["Start Date"], errors="coerce")
        # Drop any rows whose date couldn't parse — they can't be windowed reliably.
        date_mask = parsed_dates.notna() & (parsed_dates >= cutoff)
        recent = txns.loc[date_mask].copy()
        recent["_parsed_date"] = parsed_dates.loc[recent.index]

        roster_holdings: Dict[str, float] = {}
        for _, row in roster.iterrows():
            key = _normalize_name(row.get("Name"))
            if not key:
                continue
            shares = _coerce_float(row.get("Shares Owned Directly"))
            if shares is not None:
                roster_holdings[key] = shares

        outsized: List[Dict[str, Any]] = []
        full_liquidations: List[Dict[str, Any]] = []

        for _, row in recent.iterrows():
            insider_name_raw = row.get("Insider")
            position_raw = row.get("Position")
            txn_type_raw = row.get("Transaction")
            shares_transacted = _coerce_float(row.get("Shares"))
            value = _coerce_float(row.get("Value"))
            parsed_date = row.get("_parsed_date")

            date_iso = (
                parsed_date.isoformat()
                if isinstance(parsed_date, pd.Timestamp) and not pd.isna(parsed_date)
                else None
            )

            holdings = roster_holdings.get(_normalize_name(insider_name_raw))

            entry: Dict[str, Any] = {
                "date": date_iso,
                "name": str(insider_name_raw) if insider_name_raw is not None else None,
                "position": str(position_raw) if position_raw is not None else None,
                "transaction_type": (
                    str(txn_type_raw) if txn_type_raw is not None else None
                ),
                "shares_transacted": shares_transacted,
                "value": value,
            }

            if holdings is None:
                # Insider absent from roster — full liquidation bucket.
                entry["insider_current_holdings"] = 0
                entry["holdings_pct_change"] = None
                full_liquidations.append(entry)
            else:
                entry["insider_current_holdings"] = holdings
                if holdings > 0 and shares_transacted is not None:
                    entry["holdings_pct_change"] = shares_transacted / holdings
                else:
                    # Denominator is zero or numerator missing — treat like a liquidation
                    # rather than silently dropping; ratio undefined.
                    entry["holdings_pct_change"] = None
                outsized.append(entry)

        if sort == "value":
            outsized.sort(
                key=lambda r: abs(r["value"]) if r.get("value") is not None else 0.0,
                reverse=True,
            )
        else:
            outsized.sort(
                key=lambda r: abs(r["holdings_pct_change"])
                if r.get("holdings_pct_change") is not None
                else 0.0,
                reverse=True,
            )

        return {
            "ticker": ticker,
            "lookback_days": lookback_days,
            "outsized_transactions": outsized[:top_n],
            "full_liquidations": full_liquidations,
        }

    except Exception as e:
        return handle_yfinance_error(
            e, ticker, "computing outsized insider transactions"
        )
