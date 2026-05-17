"""Unit tests for ``tools.options``.

Why these tests exist
---------------------

The four options tools share a core dispatch pattern — read ``stock.options``
(a tuple of date strings), optionally validate a caller-supplied
``expiration_date``, then call ``stock.option_chain(date)`` (a METHOD, not a
property) to get an object whose ``.calls`` and ``.puts`` are DataFrames.

The load-bearing contracts are:

* When ``expiration_date`` is omitted the tools must default to
  ``options[0]`` — the nearest expiry. A regression that always uses ``None``
  or the last date would silently return stale/wrong data.
* When an explicit date is supplied but is NOT in ``options``, the tools must
  return an error response that surfaces ``available_dates`` so the caller can
  retry with a valid value.
* ``get_options_chain`` returns both ``calls`` AND ``puts``; ``get_calls``
  returns only ``calls``; ``get_puts`` returns only ``puts``. A typo that
  swaps the keys would silently feed the wrong leg to the LLM.
* An empty ``options`` tuple (no listed options) must surface an ``error``
  response rather than raising an exception.

All tests are pure-unit — ``yf.Ticker`` is replaced by a stub via
``stub_ticker_factory`` from conftest.py. No network calls are made.
"""

from __future__ import annotations

import types

import pandas as pd
import pytest

from tools import options


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_calls_df():
    """Minimal calls DataFrame matching the real yfinance schema."""
    return pd.DataFrame(
        [
            {
                "contractSymbol": "AAPL250620C00150000",
                "strike": 150.0,
                "lastPrice": 12.50,
                "bid": 12.30,
                "ask": 12.70,
                "volume": 1000,
                "openInterest": 5000,
                "impliedVolatility": 0.25,
            }
        ]
    )


def _make_puts_df():
    """Minimal puts DataFrame matching the real yfinance schema."""
    return pd.DataFrame(
        [
            {
                "contractSymbol": "AAPL250620P00150000",
                "strike": 150.0,
                "lastPrice": 3.80,
                "bid": 3.70,
                "ask": 3.90,
                "volume": 800,
                "openInterest": 3000,
                "impliedVolatility": 0.28,
            }
        ]
    )


SAMPLE_DATES = ("2025-06-20", "2025-07-18", "2025-09-19")


def make_option_chain(calls_df, puts_df, recorder):
    """Return a callable that records the date arg and yields a SimpleNamespace.

    ``recorder`` is a list; each call appends the date string so tests can
    assert which date the tool actually used.
    """

    def _fn(date):
        recorder.append(date)
        return types.SimpleNamespace(calls=calls_df, puts=puts_df)

    return _fn


# ---------------------------------------------------------------------------
# get_options_dates
# ---------------------------------------------------------------------------


class TestGetOptionsDates:
    def test_happy_path_returns_dates(self, stub_ticker_factory):
        stub_ticker_factory(options, {"options": SAMPLE_DATES})

        result = options.get_options_dates("aapl")

        assert result["ticker"] == "AAPL"  # validate_ticker_symbol normalises
        assert result["expiration_dates"] == list(SAMPLE_DATES)
        assert "error" not in result

    def test_empty_options_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(options, {"options": ()})

        result = options.get_options_dates("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"
        assert "No options" in result["message"] or "options" in result["message"].lower()

    def test_none_options_returns_error(self, stub_ticker_factory):
        """Some tickers return None for options — must not raise."""
        stub_ticker_factory(options, {"options": None})

        result = options.get_options_dates("AAPL")

        assert result["error"] is True

    def test_ticker_normalised_to_uppercase(self, stub_ticker_factory):
        stub_ticker_factory(options, {"options": SAMPLE_DATES})

        result = options.get_options_dates("aapl")

        assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# get_options_chain
# ---------------------------------------------------------------------------


class TestGetOptionsChain:
    def test_happy_path_default_date_uses_first(self, stub_ticker_factory):
        """When expiration_date is omitted, the call must use options[0]."""
        calls_df = _make_calls_df()
        puts_df = _make_puts_df()
        recorder = []

        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(calls_df, puts_df, recorder),
            },
        )

        result = options.get_options_chain("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["expiration_date"] == SAMPLE_DATES[0]
        assert recorder == [SAMPLE_DATES[0]]
        assert "calls" in result
        assert "puts" in result
        assert len(result["calls"]) == 1
        assert len(result["puts"]) == 1

    def test_explicit_valid_date_routes_correctly(self, stub_ticker_factory):
        """Supplying an explicit valid date must call option_chain with that date."""
        calls_df = _make_calls_df()
        puts_df = _make_puts_df()
        recorder = []

        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(calls_df, puts_df, recorder),
            },
        )

        target = SAMPLE_DATES[2]  # last date — not the default
        result = options.get_options_chain("AAPL", expiration_date=target)

        assert result["expiration_date"] == target
        assert recorder == [target]
        assert "error" not in result

    def test_invalid_date_returns_error_with_available_dates(self, stub_ticker_factory):
        """An expiration date not in options[] must yield error + available_dates."""
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        result = options.get_options_chain("AAPL", expiration_date="1999-01-01")

        assert result["error"] is True
        assert "available_dates" in result
        assert list(result["available_dates"]) == list(SAMPLE_DATES)
        # option_chain must NOT have been called
        assert recorder == []

    def test_no_options_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(options, {"options": ()})

        result = options.get_options_chain("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_both_legs_present_in_response(self, stub_ticker_factory):
        """Result must carry both 'calls' and 'puts' keys."""
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        result = options.get_options_chain("AAPL")

        assert "calls" in result
        assert "puts" in result


# ---------------------------------------------------------------------------
# get_calls
# ---------------------------------------------------------------------------


class TestGetCalls:
    def test_happy_path_default_date_uses_first(self, stub_ticker_factory):
        """get_calls with no date uses options[0] and returns only calls key."""
        calls_df = _make_calls_df()
        puts_df = _make_puts_df()
        recorder = []

        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(calls_df, puts_df, recorder),
            },
        )

        result = options.get_calls("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["expiration_date"] == SAMPLE_DATES[0]
        assert recorder == [SAMPLE_DATES[0]]
        assert "calls" in result
        # get_calls must NOT include puts
        assert "puts" not in result

    def test_explicit_valid_date_routes_correctly(self, stub_ticker_factory):
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        target = SAMPLE_DATES[1]
        result = options.get_calls("AAPL", expiration_date=target)

        assert result["expiration_date"] == target
        assert recorder == [target]
        assert "calls" in result
        assert "puts" not in result

    def test_invalid_date_returns_error_with_available_dates(self, stub_ticker_factory):
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        result = options.get_calls("AAPL", expiration_date="1999-01-01")

        assert result["error"] is True
        assert "available_dates" in result
        assert recorder == []

    def test_no_options_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(options, {"options": ()})

        result = options.get_calls("AAPL")

        assert result["error"] is True

    def test_calls_data_shape(self, stub_ticker_factory):
        """The calls list must preserve the strike column from the DataFrame."""
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        result = options.get_calls("AAPL")

        assert isinstance(result["calls"], list)
        assert result["calls"][0]["strike"] == 150.0


# ---------------------------------------------------------------------------
# get_puts
# ---------------------------------------------------------------------------


class TestGetPuts:
    def test_happy_path_default_date_uses_first(self, stub_ticker_factory):
        """get_puts with no date uses options[0] and returns only puts key."""
        calls_df = _make_calls_df()
        puts_df = _make_puts_df()
        recorder = []

        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(calls_df, puts_df, recorder),
            },
        )

        result = options.get_puts("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["expiration_date"] == SAMPLE_DATES[0]
        assert recorder == [SAMPLE_DATES[0]]
        assert "puts" in result
        # get_puts must NOT include calls
        assert "calls" not in result

    def test_explicit_valid_date_routes_correctly(self, stub_ticker_factory):
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        target = SAMPLE_DATES[1]
        result = options.get_puts("AAPL", expiration_date=target)

        assert result["expiration_date"] == target
        assert recorder == [target]
        assert "puts" in result
        assert "calls" not in result

    def test_invalid_date_returns_error_with_available_dates(self, stub_ticker_factory):
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        result = options.get_puts("AAPL", expiration_date="1999-01-01")

        assert result["error"] is True
        assert "available_dates" in result
        assert recorder == []

    def test_no_options_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(options, {"options": ()})

        result = options.get_puts("AAPL")

        assert result["error"] is True

    def test_puts_data_shape(self, stub_ticker_factory):
        """The puts list must preserve the strike column from the DataFrame."""
        recorder = []
        stub_ticker_factory(
            options,
            {
                "options": SAMPLE_DATES,
                "option_chain": make_option_chain(_make_calls_df(), _make_puts_df(), recorder),
            },
        )

        result = options.get_puts("AAPL")

        assert isinstance(result["puts"], list)
        assert result["puts"][0]["strike"] == 150.0
