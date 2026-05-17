"""Market-wide calendar tools for the Yahoo Finance MCP server.

Four tools live in this module:

* ``get_market_earnings_calendar`` — upcoming earnings releases across the
  market (with optional ``market_cap`` floor / ``filter_most_active`` toggle).
* ``get_market_ipo_calendar`` — upcoming IPO filings/listings.
* ``get_market_splits_calendar`` — upcoming stock-split events.
* ``get_market_economic_calendar`` — scheduled macro releases (CPI, jobs, etc).

Why these are *separate* from ``get_calendar(ticker)`` in ``analysis.py``
-----------------------------------------------------------------------

``Ticker.calendar`` returns a single company's upcoming earnings + dividend
dates — a **per-ticker** view. ``yfinance.Calendars`` (plural) is a different
data source entirely: a **market-wide** stream of four disjoint event types
over a forward date window. The ADR at
``docs/adr/0002-market-vs-company-calendar.md``
captures the decision to expose the market-wide view as four tools (not one
polymorphic tool with an ``event_type`` enum, not one tool returning all four
buckets) and to prefix them with ``get_market_`` so an LLM client can't
confuse them with the per-ticker ``get_calendar``.

Envelope
--------

Every tool returns a self-describing envelope so the LLM doesn't have to
remember which fields belong to which event type::

    {
        "event_type": "earnings" | "ipo" | "splits" | "economic",
        "days": <int>,
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "count": <int>,
        "events": [ ...rows from yfinance.Calendars... ],
    }

The window is **forward-only** from today; ``days`` is the only window
parameter on the IPO / splits / economic tools. Earnings additionally exposes
``market_cap``, ``filter_most_active`` and ``limit`` because earnings season
can overflow the LLM's context if every reporting company is returned.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

import yfinance as yf

from utils import format_dataframe_to_dict


_MAX_LIMIT = 100  # yfinance caps `size` at 100 per call (see Calendars._get_data)


def _validate_days(days: int) -> int:
    if not isinstance(days, int) or isinstance(days, bool):
        raise ValueError("days must be a positive integer")
    if days <= 0:
        raise ValueError("days must be a positive integer")
    return days


def _validate_limit(limit: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be a positive integer")
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    # Capping at the upstream YF maximum so callers get a useful response
    # rather than a silent truncation surprise downstream.
    return min(limit, _MAX_LIMIT)


def _window(days: int) -> tuple[str, str]:
    """Return (start_date, end_date) ISO strings for a forward-only window."""
    start = date.today()
    end = start + timedelta(days=days)
    return start.isoformat(), end.isoformat()


def _envelope(
    event_type: str,
    days: int,
    start_date: str,
    end_date: str,
    events: list,
) -> Dict[str, Any]:
    return {
        "event_type": event_type,
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "count": len(events),
        "events": events,
    }


def _error(operation: str, exc: Exception) -> Dict[str, Any]:
    """Calendar tools don't take a ticker, so we mirror handle_yfinance_error
    but omit the ticker field."""
    return {
        "error": True,
        "message": f"Error {operation}: {exc}",
        "operation": operation,
    }


def get_market_earnings_calendar(
    days: int = 7,
    market_cap: Optional[float] = None,
    filter_most_active: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    """Upcoming earnings calendar across the market.

    Args:
        days: Forward-only window size in days (default 7).
        market_cap: Optional intraday market-cap floor in USD. ``None`` means
            no floor.
        filter_most_active: Restrict to Yahoo's most-active tickers (default
            ``True``) — without this the response can swamp the LLM during
            earnings season.
        limit: Maximum events to return (default 50, capped at 100 by Yahoo).

    Returns:
        Envelope ``{event_type='earnings', days, start_date, end_date, count,
        events}``.
    """
    try:
        days = _validate_days(days)
        limit = _validate_limit(limit)
        if market_cap is not None:
            if not isinstance(market_cap, (int, float)) or isinstance(
                market_cap, bool
            ):
                raise ValueError("market_cap must be numeric or None")
            if market_cap < 0:
                raise ValueError("market_cap must be non-negative")
        if not isinstance(filter_most_active, bool):
            raise ValueError("filter_most_active must be a boolean")

        start_date, end_date = _window(days)

        calendars = yf.Calendars(start=start_date, end=end_date)
        df = calendars.get_earnings_calendar(
            market_cap=market_cap,
            filter_most_active=filter_most_active,
            limit=limit,
        )
        events = format_dataframe_to_dict(df)
        return _envelope("earnings", days, start_date, end_date, events)

    except Exception as e:
        return _error("fetching market earnings calendar", e)


def get_market_ipo_calendar(days: int = 7) -> Dict[str, Any]:
    """Upcoming IPO calendar across the market.

    Args:
        days: Forward-only window size in days (default 7).

    Returns:
        Envelope ``{event_type='ipo', days, start_date, end_date, count,
        events}``.
    """
    try:
        days = _validate_days(days)
        start_date, end_date = _window(days)

        calendars = yf.Calendars(start=start_date, end=end_date)
        # Underlying yfinance method is `get_ipo_info_calendar`; we expose
        # `get_market_ipo_calendar` per the ADR's tool-naming decision.
        df = calendars.get_ipo_info_calendar(limit=_MAX_LIMIT)
        events = format_dataframe_to_dict(df)
        return _envelope("ipo", days, start_date, end_date, events)

    except Exception as e:
        return _error("fetching market IPO calendar", e)


def get_market_splits_calendar(days: int = 7) -> Dict[str, Any]:
    """Upcoming stock-splits calendar across the market.

    Args:
        days: Forward-only window size in days (default 7).

    Returns:
        Envelope ``{event_type='splits', days, start_date, end_date, count,
        events}``.
    """
    try:
        days = _validate_days(days)
        start_date, end_date = _window(days)

        calendars = yf.Calendars(start=start_date, end=end_date)
        df = calendars.get_splits_calendar(limit=_MAX_LIMIT)
        events = format_dataframe_to_dict(df)
        return _envelope("splits", days, start_date, end_date, events)

    except Exception as e:
        return _error("fetching market splits calendar", e)


def get_market_economic_calendar(days: int = 7) -> Dict[str, Any]:
    """Upcoming economic-events calendar (CPI, jobs, central-bank releases, …).

    Args:
        days: Forward-only window size in days (default 7).

    Returns:
        Envelope ``{event_type='economic', days, start_date, end_date, count,
        events}``.
    """
    try:
        days = _validate_days(days)
        start_date, end_date = _window(days)

        calendars = yf.Calendars(start=start_date, end=end_date)
        # Underlying yfinance method is `get_economic_events_calendar`; we
        # expose `get_market_economic_calendar` per the ADR's tool-naming
        # decision (and the glossary entry in CONTEXT.md).
        df = calendars.get_economic_events_calendar(limit=_MAX_LIMIT)
        events = format_dataframe_to_dict(df)
        return _envelope("economic", days, start_date, end_date, events)

    except Exception as e:
        return _error("fetching market economic calendar", e)
