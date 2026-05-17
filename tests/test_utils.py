"""Unit tests for the formatting and validation primitives in ``utils.py``.

Why these tests exist
---------------------

``utils.py`` is the shared foundation every tool module builds on. A subtle
regression here — a NaN leaking through as ``float('nan')`` instead of
``None``, a numpy scalar surviving as a non-serialisable ``np.int64``, a
Timestamp not converted to ISO, or a ticker symbol not uppercased — will
silently corrupt the JSON returned to every MCP client.  Because these helpers
are exercised indirectly by the tool-level tests only for the happy paths that
yfinance happens to produce, the edge cases (None input, RangeIndex vs named
index, NaT, numpy scalars, whitespace-only symbols) are never exercised
elsewhere.

These tests pin every branch so a refactor can't accidentally change the
contract without a red test.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import utils


# ---------------------------------------------------------------------------
# format_dataframe_to_dict
# ---------------------------------------------------------------------------


class TestFormatDataframeToDict:
    def test_none_returns_empty_list(self):
        assert utils.format_dataframe_to_dict(None) == []

    def test_empty_dataframe_returns_empty_list(self):
        assert utils.format_dataframe_to_dict(pd.DataFrame()) == []

    def test_range_index_not_reset(self):
        """A plain RangeIndex should NOT be included as a column in the output."""
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = utils.format_dataframe_to_dict(df)
        assert len(result) == 2
        # RangeIndex must not appear as a column called 'index'
        assert "index" not in result[0]
        assert result[0] == {"a": 1, "b": 3}

    def test_named_index_is_reset_into_columns(self):
        """A named index (e.g. ticker symbol) is meaningful and should be included."""
        df = pd.DataFrame({"price": [100.0, 200.0]}, index=pd.Index(["AAPL", "MSFT"], name="ticker"))
        result = utils.format_dataframe_to_dict(df)
        assert len(result) == 2
        assert "ticker" in result[0]
        assert result[0]["ticker"] == "AAPL"

    def test_unnamed_non_range_index_is_reset(self):
        """A non-RangeIndex without a name still gets reset into the output."""
        df = pd.DataFrame({"val": [10]}, index=pd.Index(["X"]))
        result = utils.format_dataframe_to_dict(df)
        # After reset_index the old index column appears as 'index'
        assert len(result) == 1
        assert "index" in result[0]
        assert result[0]["index"] == "X"

    def test_timestamp_converted_to_iso_string(self):
        ts = pd.Timestamp("2024-01-15T09:30:00")
        df = pd.DataFrame({"date": [ts]})
        result = utils.format_dataframe_to_dict(df)
        assert result[0]["date"] == ts.isoformat()
        assert isinstance(result[0]["date"], str)

    def test_nan_float_converted_to_none(self):
        df = pd.DataFrame({"x": [float("nan")]})
        result = utils.format_dataframe_to_dict(df)
        assert result[0]["x"] is None

    def test_nat_converted_to_none(self):
        df = pd.DataFrame({"d": [pd.NaT]})
        result = utils.format_dataframe_to_dict(df)
        assert result[0]["d"] is None

    def test_numpy_int64_converted_to_python_int(self):
        df = pd.DataFrame({"n": np.array([42], dtype=np.int64)})
        result = utils.format_dataframe_to_dict(df)
        assert result[0]["n"] == 42
        assert isinstance(result[0]["n"], int)

    def test_numpy_float64_converted_to_python_float(self):
        df = pd.DataFrame({"f": np.array([3.14], dtype=np.float64)})
        result = utils.format_dataframe_to_dict(df)
        assert isinstance(result[0]["f"], float)
        assert math.isclose(result[0]["f"], 3.14)

    def test_mixed_row_all_types_cleaned(self):
        """One row with every special type at once — nothing leaks through raw."""
        ts = pd.Timestamp("2025-06-01")
        df = pd.DataFrame({
            "ts": [ts],
            "nan": [float("nan")],
            "nat": [pd.NaT],
            "np_int": np.array([7], dtype=np.int64),
            "plain": ["hello"],
        })
        result = utils.format_dataframe_to_dict(df)
        row = result[0]
        assert row["ts"] == ts.isoformat()
        assert row["nan"] is None
        assert row["nat"] is None
        assert row["np_int"] == 7
        assert isinstance(row["np_int"], int)
        assert row["plain"] == "hello"

    def test_multiple_rows_preserved(self):
        df = pd.DataFrame({"v": [1, 2, 3]})
        result = utils.format_dataframe_to_dict(df)
        assert len(result) == 3
        assert [r["v"] for r in result] == [1, 2, 3]


# ---------------------------------------------------------------------------
# format_series_to_dict
# ---------------------------------------------------------------------------


class TestFormatSeriesToDict:
    def test_none_returns_empty_dict(self):
        assert utils.format_series_to_dict(None) == {}

    def test_empty_series_returns_empty_dict(self):
        assert utils.format_series_to_dict(pd.Series([], dtype=object)) == {}

    def test_timestamp_value_converted_to_iso(self):
        ts = pd.Timestamp("2024-03-20T12:00:00")
        s = pd.Series({"event": ts})
        result = utils.format_series_to_dict(s)
        assert result["event"] == ts.isoformat()
        assert isinstance(result["event"], str)

    def test_nan_value_converted_to_none(self):
        s = pd.Series({"x": float("nan")})
        result = utils.format_series_to_dict(s)
        assert result["x"] is None

    def test_numpy_scalar_converted(self):
        s = pd.Series({"n": np.int64(99)})
        result = utils.format_series_to_dict(s)
        assert result["n"] == 99
        assert isinstance(result["n"], int)

    def test_plain_string_passthrough(self):
        s = pd.Series({"name": "Apple Inc."})
        result = utils.format_series_to_dict(s)
        assert result["name"] == "Apple Inc."

    def test_mixed_values(self):
        ts = pd.Timestamp("2025-01-01")
        s = pd.Series({
            "ts": ts,
            "nan_val": float("nan"),
            "np_val": np.int32(5),
            "str_val": "hello",
        })
        result = utils.format_series_to_dict(s)
        assert result["ts"] == ts.isoformat()
        assert result["nan_val"] is None
        assert result["np_val"] == 5
        assert isinstance(result["np_val"], int)
        assert result["str_val"] == "hello"


# ---------------------------------------------------------------------------
# safe_get_ticker_info
# ---------------------------------------------------------------------------


class TestSafeGetTickerInfo:
    def test_returns_attribute_when_present(self):
        class Obj:
            price = 150.0

        assert utils.safe_get_ticker_info(Obj(), "price", default=0.0) == 150.0

    def test_none_value_returns_default(self):
        class Obj:
            price = None

        assert utils.safe_get_ticker_info(Obj(), "price", default=99) == 99

    def test_missing_attribute_returns_default(self):
        """``getattr`` with a default never raises; safe_get_ticker_info returns default."""
        class Obj:
            pass

        assert utils.safe_get_ticker_info(Obj(), "nonexistent", default="fallback") == "fallback"

    def test_exception_during_getattr_returns_default(self):
        """A property that raises on access must be caught and return default."""

        class Broken:
            @property
            def exploding(self):
                raise RuntimeError("network error")

        result = utils.safe_get_ticker_info(Broken(), "exploding", default="safe")
        assert result == "safe"

    def test_none_object_returns_default(self):
        """Passing None as the ticker object should return the default, not raise."""
        result = utils.safe_get_ticker_info(None, "anything", default="d")
        assert result == "d"

    def test_default_is_none_when_not_provided(self):
        class Obj:
            x = None

        assert utils.safe_get_ticker_info(Obj(), "x") is None


# ---------------------------------------------------------------------------
# validate_ticker_symbol
# ---------------------------------------------------------------------------


class TestValidateTickerSymbol:
    def test_valid_symbol_uppercased(self):
        assert utils.validate_ticker_symbol("aapl") == "AAPL"

    def test_strips_surrounding_whitespace(self):
        assert utils.validate_ticker_symbol("  aapl  ") == "AAPL"

    def test_already_upper_passthrough(self):
        assert utils.validate_ticker_symbol("MSFT") == "MSFT"

    def test_none_raises_value_error(self):
        with pytest.raises(ValueError):
            utils.validate_ticker_symbol(None)

    def test_non_string_raises_value_error(self):
        with pytest.raises(ValueError):
            utils.validate_ticker_symbol(123)

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            utils.validate_ticker_symbol("")

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError):
            utils.validate_ticker_symbol("   ")

    def test_list_raises_value_error(self):
        with pytest.raises(ValueError):
            utils.validate_ticker_symbol(["AAPL"])


# ---------------------------------------------------------------------------
# validate_period
# ---------------------------------------------------------------------------


class TestValidatePeriod:
    _VALID = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]

    @pytest.mark.parametrize("period", _VALID)
    def test_valid_period_accepted(self, period):
        assert utils.validate_period(period) == period

    @pytest.mark.parametrize("bad", ["1w", "6m", "1year", "daily", "", "MAX", "1D"])
    def test_invalid_period_raises(self, bad):
        with pytest.raises(ValueError):
            utils.validate_period(bad)


# ---------------------------------------------------------------------------
# validate_interval
# ---------------------------------------------------------------------------


class TestValidateInterval:
    _VALID = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]

    @pytest.mark.parametrize("interval", _VALID)
    def test_valid_interval_accepted(self, interval):
        assert utils.validate_interval(interval) == interval

    @pytest.mark.parametrize("bad", ["1min", "4h", "1week", "", "1M", "1D", "daily"])
    def test_invalid_interval_raises(self, bad):
        with pytest.raises(ValueError):
            utils.validate_interval(bad)


# ---------------------------------------------------------------------------
# handle_yfinance_error
# ---------------------------------------------------------------------------


class TestHandleYfinanceError:
    def test_returns_error_true(self):
        result = utils.handle_yfinance_error(ValueError("boom"), "AAPL", "fetching info")
        assert result["error"] is True

    def test_ticker_preserved(self):
        result = utils.handle_yfinance_error(RuntimeError("x"), "TSLA", "fetching history")
        assert result["ticker"] == "TSLA"

    def test_operation_preserved(self):
        result = utils.handle_yfinance_error(RuntimeError("x"), "TSLA", "fetching history")
        assert result["operation"] == "fetching history"

    def test_message_format(self):
        """Message must follow the canonical template used by all tools."""
        e = Exception("connection refused")
        result = utils.handle_yfinance_error(e, "GOOG", "fetching dividends")
        assert result["message"] == "Error fetching dividends for GOOG: connection refused"

    def test_all_keys_present(self):
        result = utils.handle_yfinance_error(Exception("e"), "X", "op")
        assert set(result.keys()) == {"error", "message", "ticker", "operation"}

    def test_exception_text_included_in_message(self):
        result = utils.handle_yfinance_error(RuntimeError("something went wrong"), "FB", "op")
        assert "something went wrong" in result["message"]


# ---------------------------------------------------------------------------
# format_financial_statement
# ---------------------------------------------------------------------------


class TestFormatFinancialStatement:
    def test_none_input_returns_empty_envelope(self):
        result = utils.format_financial_statement(None, "income_statement")
        assert result == {
            "statement_type": "income_statement",
            "periods": [],
            "data": [],
        }

    def test_empty_dataframe_returns_empty_envelope(self):
        result = utils.format_financial_statement(pd.DataFrame(), "balance_sheet")
        assert result == {
            "statement_type": "balance_sheet",
            "periods": [],
            "data": [],
        }

    def test_statement_type_passthrough(self):
        result = utils.format_financial_statement(None, "cash_flow")
        assert result["statement_type"] == "cash_flow"

    def test_timestamp_columns_become_iso_periods(self):
        """Columns are dates; after transposition they become the period index."""
        dates = [pd.Timestamp("2023-12-31"), pd.Timestamp("2022-12-31")]
        df = pd.DataFrame(
            {dates[0]: [1_000.0, 500.0], dates[1]: [900.0, 450.0]},
            index=pd.Index(["Revenue", "NetIncome"], name="Breakdown"),
        )
        result = utils.format_financial_statement(df, "income_statement")
        assert result["periods"] == [d.isoformat() for d in dates]

    def test_string_columns_become_str_periods(self):
        """Non-Timestamp column labels are cast with str()."""
        df = pd.DataFrame(
            {"Q1": [100.0], "Q2": [200.0]},
            index=pd.Index(["Revenue"], name="Breakdown"),
        )
        result = utils.format_financial_statement(df, "income_statement")
        assert result["periods"] == ["Q1", "Q2"]

    def test_data_is_transposed_list_of_dicts(self):
        """Input has dates as columns and line items as rows.
        Output data is the transposed frame — each element corresponds to one period."""
        dates = [pd.Timestamp("2023-12-31"), pd.Timestamp("2022-12-31")]
        df = pd.DataFrame(
            {dates[0]: [1_000.0, 500.0], dates[1]: [900.0, 450.0]},
            index=pd.Index(["Revenue", "NetIncome"], name="Breakdown"),
        )
        result = utils.format_financial_statement(df, "income_statement")
        # Two periods -> two dicts in data
        assert len(result["data"]) == 2
        # Each dict must contain line-item columns
        assert "Revenue" in result["data"][0]
        assert "NetIncome" in result["data"][0]

    def test_data_values_match_transposed_values(self):
        """The numbers in the output dicts must match the transposed DataFrame."""
        dates = [pd.Timestamp("2023-12-31"), pd.Timestamp("2022-12-31")]
        df = pd.DataFrame(
            {dates[0]: [1_000.0, 500.0], dates[1]: [900.0, 450.0]},
            index=pd.Index(["Revenue", "NetIncome"], name="Breakdown"),
        )
        result = utils.format_financial_statement(df, "income_statement")
        # First period: 2023-12-31 row
        assert math.isclose(result["data"][0]["Revenue"], 1_000.0)
        assert math.isclose(result["data"][0]["NetIncome"], 500.0)
        # Second period: 2022-12-31 row
        assert math.isclose(result["data"][1]["Revenue"], 900.0)
        assert math.isclose(result["data"][1]["NetIncome"], 450.0)

    def test_envelope_keys_always_present(self):
        result = utils.format_financial_statement(None, "balance_sheet")
        assert "statement_type" in result
        assert "periods" in result
        assert "data" in result
