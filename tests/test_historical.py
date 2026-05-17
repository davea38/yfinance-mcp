"""Unit tests for ``tools.historical``.

Why these tests exist
---------------------

The five historical tools form the backbone of time-series access in the MCP
server. Several subtle contracts are easy to break silently:

* ``get_historical_data`` is the only tool that calls a *method* (``history``)
  rather than reading a property.  Period and interval parameters must be
  validated *before* the yfinance call (so the error surfaces from
  ``handle_yfinance_error``, not a raw yfinance exception), and the validated
  values must be forwarded as keyword args — not positionally.

* ``get_dividends``, ``get_splits``, ``get_actions``, and ``get_capital_gains``
  all return ``data: []`` plus a human-readable ``message`` on empty/None
  input — they do NOT set ``error: True``.  A refactor that changed any of
  them to mirror the error protocol used by ``get_historical_data`` would
  silently break LLM response parsing.

* Ticker normalisation (``"aapl"`` -> ``"AAPL"``) must happen in every tool
  before the yfinance call so the returned ``ticker`` key is always uppercase.

* ``get_splits`` serialises the ratio as a *string*, not a float — clients
  must not have to handle type ambiguity.

* ``get_capital_gains`` is the ETF/fund sibling of dividends; it must follow
  the same empty-data shape even though it's rarely populated for plain stocks.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tools import historical


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _price_df() -> pd.DataFrame:
    """Minimal OHLCV DataFrame that satisfies ``format_dataframe_to_dict``."""
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date")
    return pd.DataFrame(
        {
            "Open": [185.0, 186.0],
            "High": [187.0, 188.0],
            "Low": [184.0, 185.0],
            "Close": [186.0, 187.0],
            "Volume": [50_000_000, 55_000_000],
        },
        index=idx,
    )


def _dividend_series() -> pd.Series:
    return pd.Series(
        [0.22, 0.24],
        index=pd.DatetimeIndex(["2024-01-15", "2024-04-15"]),
        name="Dividends",
    )


def _split_series() -> pd.Series:
    return pd.Series(
        [4.0, 2.0],
        index=pd.DatetimeIndex(["2020-08-31", "2022-06-10"]),
        name="Stock Splits",
    )


def _actions_df() -> pd.DataFrame:
    idx = pd.DatetimeIndex(["2024-01-15", "2024-04-15"], name="Date")
    return pd.DataFrame(
        {"Dividends": [0.22, 0.24], "Stock Splits": [0.0, 0.0]},
        index=idx,
    )


def _capital_gains_series() -> pd.Series:
    return pd.Series(
        [1.05, 0.87],
        index=pd.DatetimeIndex(["2023-12-20", "2022-12-21"]),
        name="Capital Gains",
    )


# ---------------------------------------------------------------------------
# get_historical_data
# ---------------------------------------------------------------------------


class TestGetHistoricalData:
    def test_happy_path_returns_ticker_period_interval_data(self, stub_ticker_factory):
        """Valid inputs -> dict with ticker, period, interval, data keys."""
        df = _price_df()
        stub_ticker_factory(historical, {"history": lambda **kw: df})

        result = historical.get_historical_data("AAPL", period="1mo", interval="1d")

        assert result["ticker"] == "AAPL"
        assert result["period"] == "1mo"
        assert result["interval"] == "1d"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2
        assert "error" not in result

    def test_period_and_interval_forwarded_as_kwargs(self, stub_ticker_factory):
        """The validated period and interval must arrive at ``stock.history`` as
        keyword arguments (not positional), exactly as specified."""
        calls: list[dict] = []

        def recording_history(**kwargs):
            calls.append(kwargs)
            return _price_df()

        stub_ticker_factory(historical, {"history": recording_history})

        historical.get_historical_data("AAPL", period="3mo", interval="1wk")

        assert len(calls) == 1
        assert calls[0]["period"] == "3mo"
        assert calls[0]["interval"] == "1wk"

    def test_ticker_normalised_to_uppercase(self, stub_ticker_factory):
        """Lowercase ticker input must be upper-cased before being returned."""
        stub_ticker_factory(historical, {"history": lambda **kw: _price_df()})

        result = historical.get_historical_data("aapl")
        assert result["ticker"] == "AAPL"

    def test_invalid_period_returns_error_true(self, stub_ticker_factory):
        """An unrecognised period must return ``error: True`` via
        ``handle_yfinance_error``, not raise an exception to the caller."""
        # The stub is set up but should never be reached because validate_period
        # raises ValueError before yf.Ticker is constructed.
        stub_ticker_factory(historical, {"history": lambda **kw: _price_df()})

        result = historical.get_historical_data("AAPL", period="99y")

        assert result.get("error") is True

    def test_invalid_interval_returns_error_true(self, stub_ticker_factory):
        """An unrecognised interval must return ``error: True``."""
        stub_ticker_factory(historical, {"history": lambda **kw: _price_df()})

        result = historical.get_historical_data("AAPL", interval="2h")

        assert result.get("error") is True

    def test_empty_dataframe_returns_error_true(self, stub_ticker_factory):
        """``stock.history()`` returning an empty DataFrame -> ``error: True``."""
        stub_ticker_factory(historical, {"history": lambda **kw: pd.DataFrame()})

        result = historical.get_historical_data("AAPL")

        assert result.get("error") is True
        assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# get_dividends
# ---------------------------------------------------------------------------


class TestGetDividends:
    def test_happy_path_returns_date_and_amount(self, stub_ticker_factory):
        """Non-empty Series -> list of ``{date, amount}`` dicts."""
        stub_ticker_factory(historical, {"dividends": _dividend_series()})

        result = historical.get_dividends("AAPL")

        assert result["ticker"] == "AAPL"
        assert "error" not in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2

        first = result["data"][0]
        assert "date" in first
        assert "amount" in first
        assert isinstance(first["amount"], float)

    def test_ticker_normalised(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"dividends": _dividend_series()})
        result = historical.get_dividends("aapl")
        assert result["ticker"] == "AAPL"

    def test_empty_series_returns_message_not_error(self, stub_ticker_factory):
        """Empty Series must return ``data: []`` plus a ``message`` key — NOT
        ``error: True``.  This is the contract that distinguishes dividends from
        the historical tool's error protocol."""
        stub_ticker_factory(historical, {"dividends": pd.Series([], dtype=float)})

        result = historical.get_dividends("AAPL")

        assert result.get("error") is not True
        assert result["data"] == []
        assert "message" in result
        assert result["ticker"] == "AAPL"

    def test_none_dividends_returns_message_not_error(self, stub_ticker_factory):
        """``None`` from yfinance must also yield the no-data message shape."""
        stub_ticker_factory(historical, {"dividends": None})

        result = historical.get_dividends("AAPL")

        assert result.get("error") is not True
        assert result["data"] == []


# ---------------------------------------------------------------------------
# get_splits
# ---------------------------------------------------------------------------


class TestGetSplits:
    def test_happy_path_returns_date_and_split_ratio_as_string(self, stub_ticker_factory):
        """Non-empty Series -> list of ``{date, split_ratio}`` where
        ``split_ratio`` is serialised as a *string* (not float/int)."""
        stub_ticker_factory(historical, {"splits": _split_series()})

        result = historical.get_splits("AAPL")

        assert result["ticker"] == "AAPL"
        assert "error" not in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2

        first = result["data"][0]
        assert "date" in first
        assert "split_ratio" in first
        assert isinstance(first["split_ratio"], str)

    def test_ticker_normalised(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"splits": _split_series()})
        result = historical.get_splits("aapl")
        assert result["ticker"] == "AAPL"

    def test_empty_series_returns_message_not_error(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"splits": pd.Series([], dtype=float)})

        result = historical.get_splits("AAPL")

        assert result.get("error") is not True
        assert result["data"] == []
        assert "message" in result

    def test_none_splits_returns_message_not_error(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"splits": None})

        result = historical.get_splits("AAPL")

        assert result.get("error") is not True
        assert result["data"] == []


# ---------------------------------------------------------------------------
# get_actions
# ---------------------------------------------------------------------------


class TestGetActions:
    def test_happy_path_returns_ticker_and_data_list(self, stub_ticker_factory):
        """Non-empty DataFrame -> ``{ticker, data: [...]}``."""
        stub_ticker_factory(historical, {"actions": _actions_df()})

        result = historical.get_actions("AAPL")

        assert result["ticker"] == "AAPL"
        assert "error" not in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2

    def test_ticker_normalised(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"actions": _actions_df()})
        result = historical.get_actions("aapl")
        assert result["ticker"] == "AAPL"

    def test_empty_dataframe_returns_message_not_error(self, stub_ticker_factory):
        """Empty DataFrame must return ``data: []`` and a ``message`` — NOT
        ``error: True``."""
        stub_ticker_factory(historical, {"actions": pd.DataFrame()})

        result = historical.get_actions("AAPL")

        assert result.get("error") is not True
        assert result["data"] == []
        assert "message" in result

    def test_none_actions_returns_message_not_error(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"actions": None})

        result = historical.get_actions("AAPL")

        assert result.get("error") is not True
        assert result["data"] == []


# ---------------------------------------------------------------------------
# get_capital_gains
# ---------------------------------------------------------------------------


class TestGetCapitalGains:
    def test_happy_path_returns_date_and_amount(self, stub_ticker_factory):
        """Non-empty Series -> list of ``{date, amount}`` dicts."""
        stub_ticker_factory(historical, {"capital_gains": _capital_gains_series()})

        result = historical.get_capital_gains("SPY")

        assert result["ticker"] == "SPY"
        assert "error" not in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2

        first = result["data"][0]
        assert "date" in first
        assert "amount" in first
        assert isinstance(first["amount"], float)

    def test_ticker_normalised(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"capital_gains": _capital_gains_series()})
        result = historical.get_capital_gains("spy")
        assert result["ticker"] == "SPY"

    def test_empty_series_returns_message_not_error(self, stub_ticker_factory):
        """Capital-gains empty path must match the dividends contract:
        ``data: []`` + ``message``, never ``error: True``."""
        stub_ticker_factory(historical, {"capital_gains": pd.Series([], dtype=float)})

        result = historical.get_capital_gains("SPY")

        assert result.get("error") is not True
        assert result["data"] == []
        assert "message" in result

    def test_none_capital_gains_returns_message_not_error(self, stub_ticker_factory):
        stub_ticker_factory(historical, {"capital_gains": None})

        result = historical.get_capital_gains("SPY")

        assert result.get("error") is not True
        assert result["data"] == []
