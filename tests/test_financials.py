"""Unit tests for ``tools.financials``.

Why these tests exist
---------------------

The four financial-statement tools are the primary way an LLM gets structured
accounting data for a ticker.  Their *envelope shape* is load-bearing in two
ways:

* Downstream prompt templates index into ``periods``, ``data``, ``ticker``,
  ``frequency``, and ``statement_type`` by key.  An accidental rename (e.g.
  ``periods`` -> ``dates``) silently breaks every prompt that formats or
  compares multiple periods.

* ``format_financial_statement`` **transposes** the raw DataFrame so that
  *dates* become rows (``periods``) and *line items* become columns inside
  ``data``.  A regression that forgets the transpose would swap rows and
  columns, producing line-item keys instead of date strings in ``periods`` and
  date strings as column headers inside each data record.

* The ``frequency`` parameter gates which yfinance attribute is read
  (``quarterly_income_stmt`` vs ``income_stmt``, etc.).  A mix-up silently
  returns the wrong cadence without raising an exception.

* ``get_financials`` is a bundle: it calls all three statement functions and
  nests the results.  A partial error in one sub-statement (e.g. empty balance
  sheet) must not blow up the whole bundle — the caller gets error objects for
  the failed sub-statement and real data for the others.

These tests also guard the *invalid-frequency* and *empty-data* error paths
because both are silent failures in production: yfinance returns an empty
DataFrame rather than raising, and an unsupported frequency string would
otherwise reach the attribute lookup and raise AttributeError.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tools import financials


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_income_stmt() -> pd.DataFrame:
    """Return a minimal income-statement DataFrame in yfinance orientation.

    Rows = line items, columns = period Timestamps (newest first).
    """
    return pd.DataFrame(
        [
            [100.0, 90.0],
            [60.0, 55.0],
            [40.0, 35.0],
        ],
        index=["Total Revenue", "Cost Of Revenue", "Gross Profit"],
        columns=[pd.Timestamp("2024-12-31"), pd.Timestamp("2024-09-30")],
    )


def _make_balance_sheet() -> pd.DataFrame:
    return pd.DataFrame(
        [
            [200.0, 180.0],
            [120.0, 110.0],
            [80.0, 70.0],
        ],
        index=["Total Assets", "Total Liabilities Net Minority Interest", "Stockholders Equity"],
        columns=[pd.Timestamp("2024-12-31"), pd.Timestamp("2024-09-30")],
    )


def _make_cash_flow() -> pd.DataFrame:
    return pd.DataFrame(
        [
            [50.0, 45.0],
            [-20.0, -18.0],
            [30.0, 27.0],
        ],
        index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"],
        columns=[pd.Timestamp("2024-12-31"), pd.Timestamp("2024-09-30")],
    )


# ---------------------------------------------------------------------------
# get_income_statement
# ---------------------------------------------------------------------------


class TestGetIncomeStatement:
    """Happy paths (quarterly + annual), empty-data error, invalid-frequency error."""

    def test_quarterly_happy_path_envelope_shape(self, stub_ticker_factory):
        """Quarterly path reads quarterly_income_stmt; envelope has all required keys."""
        df = _make_income_stmt()
        stub_ticker_factory(financials, {"quarterly_income_stmt": df})

        result = financials.get_income_statement("aapl", frequency="quarterly")

        assert result["ticker"] == "AAPL"
        assert result["frequency"] == "quarterly"
        assert result["statement_type"] == "income_statement"
        # Two period columns -> two period strings
        assert len(result["periods"]) == 2
        assert result["periods"][0] == pd.Timestamp("2024-12-31").isoformat()
        assert result["periods"][1] == pd.Timestamp("2024-09-30").isoformat()
        # data is a list of records, one per period
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2
        # Each record must contain at least one line-item key
        first = result["data"][0]
        assert "Total Revenue" in first
        assert first["Total Revenue"] == 100.0

    def test_annual_happy_path_reads_income_stmt(self, stub_ticker_factory):
        """Annual path reads income_stmt (not the quarterly_ variant)."""
        df = _make_income_stmt()
        # Only provide the annual attribute; quarterly must not be accessed
        stub_ticker_factory(financials, {"income_stmt": df})

        result = financials.get_income_statement("MSFT", frequency="annual")

        assert result["ticker"] == "MSFT"
        assert result["frequency"] == "annual"
        assert result["statement_type"] == "income_statement"
        assert len(result["periods"]) == 2

    def test_quarterly_uses_quarterly_attribute_not_annual(self, stub_ticker_factory):
        """Confirm frequency routing: quarterly path must NOT fall through to income_stmt."""
        df = _make_income_stmt()
        stub_ticker_factory(financials, {"quarterly_income_stmt": df})
        # If the routing is wrong, accessing the missing 'income_stmt' attr raises AttributeError.
        result = financials.get_income_statement("AAPL", frequency="quarterly")
        assert "error" not in result or result.get("error") is not True

    def test_empty_dataframe_returns_error(self, stub_ticker_factory):
        """Empty DataFrame from yfinance must produce error: True."""
        stub_ticker_factory(financials, {"quarterly_income_stmt": pd.DataFrame()})

        result = financials.get_income_statement("AAPL", frequency="quarterly")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_none_statement_returns_error(self, stub_ticker_factory):
        """None statement must produce error: True."""
        stub_ticker_factory(financials, {"quarterly_income_stmt": None})

        result = financials.get_income_statement("AAPL", frequency="quarterly")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    @pytest.mark.parametrize("bad_freq", ["monthly", "weekly", "q", "", "QUARTERLY"])
    def test_invalid_frequency_returns_error(self, stub_ticker_factory, bad_freq):
        """Any frequency other than 'quarterly'/'annual' must return error: True."""
        stub_ticker_factory(financials, {})

        result = financials.get_income_statement("AAPL", frequency=bad_freq)

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_ticker_is_normalised_to_uppercase(self, stub_ticker_factory):
        stub_ticker_factory(financials, {"quarterly_income_stmt": _make_income_stmt()})
        result = financials.get_income_statement("aapl")
        assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# get_balance_sheet
# ---------------------------------------------------------------------------


class TestGetBalanceSheet:
    def test_quarterly_happy_path_envelope_shape(self, stub_ticker_factory):
        df = _make_balance_sheet()
        stub_ticker_factory(financials, {"quarterly_balance_sheet": df})

        result = financials.get_balance_sheet("aapl", frequency="quarterly")

        assert result["ticker"] == "AAPL"
        assert result["frequency"] == "quarterly"
        assert result["statement_type"] == "balance_sheet"
        assert len(result["periods"]) == 2
        assert result["periods"][0] == pd.Timestamp("2024-12-31").isoformat()
        first = result["data"][0]
        assert "Total Assets" in first
        assert first["Total Assets"] == 200.0

    def test_annual_happy_path_reads_balance_sheet(self, stub_ticker_factory):
        df = _make_balance_sheet()
        stub_ticker_factory(financials, {"balance_sheet": df})

        result = financials.get_balance_sheet("GOOGL", frequency="annual")

        assert result["ticker"] == "GOOGL"
        assert result["frequency"] == "annual"
        assert result["statement_type"] == "balance_sheet"
        assert len(result["periods"]) == 2

    def test_quarterly_does_not_fall_through_to_annual(self, stub_ticker_factory):
        """Routing guard: quarterly must use quarterly_balance_sheet."""
        stub_ticker_factory(financials, {"quarterly_balance_sheet": _make_balance_sheet()})
        result = financials.get_balance_sheet("AAPL", frequency="quarterly")
        assert "error" not in result or result.get("error") is not True

    def test_empty_dataframe_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(financials, {"quarterly_balance_sheet": pd.DataFrame()})
        result = financials.get_balance_sheet("AAPL", frequency="quarterly")
        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_none_statement_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(financials, {"quarterly_balance_sheet": None})
        result = financials.get_balance_sheet("AAPL", frequency="quarterly")
        assert result["error"] is True

    @pytest.mark.parametrize("bad_freq", ["monthly", "daily", "a", "Annual"])
    def test_invalid_frequency_returns_error(self, stub_ticker_factory, bad_freq):
        stub_ticker_factory(financials, {})
        result = financials.get_balance_sheet("AAPL", frequency=bad_freq)
        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_data_records_contain_line_items_as_keys(self, stub_ticker_factory):
        """After transpose each data record has line-item names as keys."""
        stub_ticker_factory(financials, {"quarterly_balance_sheet": _make_balance_sheet()})
        result = financials.get_balance_sheet("AAPL")
        assert "Stockholders Equity" in result["data"][0]


# ---------------------------------------------------------------------------
# get_cash_flow
# ---------------------------------------------------------------------------


class TestGetCashFlow:
    def test_quarterly_happy_path_envelope_shape(self, stub_ticker_factory):
        df = _make_cash_flow()
        stub_ticker_factory(financials, {"quarterly_cashflow": df})

        result = financials.get_cash_flow("aapl", frequency="quarterly")

        assert result["ticker"] == "AAPL"
        assert result["frequency"] == "quarterly"
        assert result["statement_type"] == "cash_flow"
        assert len(result["periods"]) == 2
        assert result["periods"][0] == pd.Timestamp("2024-12-31").isoformat()
        first = result["data"][0]
        assert "Operating Cash Flow" in first
        assert first["Operating Cash Flow"] == 50.0

    def test_annual_happy_path_reads_cashflow(self, stub_ticker_factory):
        df = _make_cash_flow()
        stub_ticker_factory(financials, {"cashflow": df})

        result = financials.get_cash_flow("TSLA", frequency="annual")

        assert result["ticker"] == "TSLA"
        assert result["frequency"] == "annual"
        assert result["statement_type"] == "cash_flow"
        assert len(result["periods"]) == 2

    def test_quarterly_uses_quarterly_cashflow_attribute(self, stub_ticker_factory):
        """quarterly path reads quarterly_cashflow, not cashflow."""
        stub_ticker_factory(financials, {"quarterly_cashflow": _make_cash_flow()})
        result = financials.get_cash_flow("AAPL", frequency="quarterly")
        assert "error" not in result or result.get("error") is not True

    def test_empty_dataframe_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(financials, {"quarterly_cashflow": pd.DataFrame()})
        result = financials.get_cash_flow("AAPL", frequency="quarterly")
        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_none_statement_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(financials, {"quarterly_cashflow": None})
        result = financials.get_cash_flow("AAPL", frequency="quarterly")
        assert result["error"] is True

    @pytest.mark.parametrize("bad_freq", ["monthly", "week", "", "Quarterly", "ANNUAL"])
    def test_invalid_frequency_returns_error(self, stub_ticker_factory, bad_freq):
        stub_ticker_factory(financials, {})
        result = financials.get_cash_flow("AAPL", frequency=bad_freq)
        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_negative_capex_survives_serialisation(self, stub_ticker_factory):
        """Negative values (CapEx is conventionally negative) must not be coerced."""
        stub_ticker_factory(financials, {"quarterly_cashflow": _make_cash_flow()})
        result = financials.get_cash_flow("AAPL")
        capex = result["data"][0].get("Capital Expenditure")
        assert capex == -20.0


# ---------------------------------------------------------------------------
# get_financials (bundle)
# ---------------------------------------------------------------------------


class TestGetFinancials:
    """get_financials calls all three sub-tools and bundles the results."""

    def _full_attrs(self, freq="quarterly"):
        """Return a StubTicker attrs dict with all six statement attributes."""
        if freq == "quarterly":
            return {
                "quarterly_income_stmt": _make_income_stmt(),
                "quarterly_balance_sheet": _make_balance_sheet(),
                "quarterly_cashflow": _make_cash_flow(),
            }
        return {
            "income_stmt": _make_income_stmt(),
            "balance_sheet": _make_balance_sheet(),
            "cashflow": _make_cash_flow(),
        }

    def test_quarterly_bundle_top_level_keys(self, stub_ticker_factory):
        """Bundle must have ticker, frequency, income_statement, balance_sheet, cash_flow."""
        stub_ticker_factory(financials, self._full_attrs("quarterly"))

        result = financials.get_financials("aapl", frequency="quarterly")

        assert result["ticker"] == "AAPL"
        assert result["frequency"] == "quarterly"
        assert "income_statement" in result
        assert "balance_sheet" in result
        assert "cash_flow" in result

    def test_annual_bundle_top_level_keys(self, stub_ticker_factory):
        stub_ticker_factory(financials, self._full_attrs("annual"))

        result = financials.get_financials("MSFT", frequency="annual")

        assert result["ticker"] == "MSFT"
        assert result["frequency"] == "annual"
        assert "income_statement" in result
        assert "balance_sheet" in result
        assert "cash_flow" in result

    def test_sub_statements_have_correct_statement_type(self, stub_ticker_factory):
        """Each sub-result carries its own statement_type discriminator."""
        stub_ticker_factory(financials, self._full_attrs("quarterly"))
        result = financials.get_financials("AAPL")

        assert result["income_statement"]["statement_type"] == "income_statement"
        assert result["balance_sheet"]["statement_type"] == "balance_sheet"
        assert result["cash_flow"]["statement_type"] == "cash_flow"

    def test_sub_statements_have_periods(self, stub_ticker_factory):
        """Each sub-result must expose ``periods`` with the date strings."""
        stub_ticker_factory(financials, self._full_attrs("quarterly"))
        result = financials.get_financials("AAPL")

        for key in ("income_statement", "balance_sheet", "cash_flow"):
            sub = result[key]
            assert "periods" in sub
            assert len(sub["periods"]) == 2

    def test_sub_statements_have_data(self, stub_ticker_factory):
        """Each sub-result must expose ``data`` as a non-empty list."""
        stub_ticker_factory(financials, self._full_attrs("quarterly"))
        result = financials.get_financials("AAPL")

        for key in ("income_statement", "balance_sheet", "cash_flow"):
            assert isinstance(result[key]["data"], list)
            assert len(result[key]["data"]) > 0

    def test_partial_error_does_not_blow_up_bundle(self, stub_ticker_factory):
        """If balance sheet is empty, bundle still returns; the sub-result carries
        error: True while the other two sub-results carry real data."""
        stub_ticker_factory(
            financials,
            {
                "quarterly_income_stmt": _make_income_stmt(),
                "quarterly_balance_sheet": pd.DataFrame(),  # empty -> error
                "quarterly_cashflow": _make_cash_flow(),
            },
        )
        result = financials.get_financials("AAPL", frequency="quarterly")

        # Top-level must not carry error: True
        assert result.get("error") is not True
        assert result["ticker"] == "AAPL"
        # The empty sub-result should be an error object
        assert result["balance_sheet"].get("error") is True
        # The non-empty sub-results should not be errors
        assert result["income_statement"].get("error") is not True
        assert result["cash_flow"].get("error") is not True

    def test_invalid_frequency_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(financials, {})
        result = financials.get_financials("AAPL", frequency="monthly")
        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    @pytest.mark.parametrize("bad_freq", ["weekly", "q", "", "QUARTERLY", "Annual"])
    def test_various_invalid_frequencies(self, stub_ticker_factory, bad_freq):
        stub_ticker_factory(financials, {})
        result = financials.get_financials("AAPL", frequency=bad_freq)
        assert result["error"] is True

    def test_ticker_normalised_in_bundle(self, stub_ticker_factory):
        stub_ticker_factory(financials, self._full_attrs("quarterly"))
        result = financials.get_financials("aapl")
        assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Transpose contract (format_financial_statement)
# ---------------------------------------------------------------------------


class TestTransposeContract:
    """Guard the transpose: periods must be date strings, data keys must be
    line-item names — not the other way around."""

    def test_periods_are_date_strings_not_line_items(self, stub_ticker_factory):
        stub_ticker_factory(
            financials, {"quarterly_income_stmt": _make_income_stmt()}
        )
        result = financials.get_income_statement("AAPL")

        for period in result["periods"]:
            # Each period string must parse as an ISO datetime, not a line-item name.
            assert "Revenue" not in period
            assert "Profit" not in period
            # Should start with a 4-digit year
            assert period[:4].isdigit(), f"Expected ISO date, got: {period!r}"

    def test_data_record_keys_are_line_items_not_dates(self, stub_ticker_factory):
        stub_ticker_factory(
            financials, {"quarterly_income_stmt": _make_income_stmt()}
        )
        result = financials.get_income_statement("AAPL")

        first_record = result["data"][0]
        # Line-item names should be present as keys
        assert "Total Revenue" in first_record
        # Period timestamps must NOT appear as keys
        for key in first_record:
            assert not key.startswith("2024"), (
                f"Date string appeared as a data key (transpose missing?): {key!r}"
            )

    def test_each_data_record_corresponds_to_one_period(self, stub_ticker_factory):
        """len(data) == len(periods) — one record per period, not per line item."""
        stub_ticker_factory(
            financials, {"quarterly_income_stmt": _make_income_stmt()}
        )
        result = financials.get_income_statement("AAPL")
        assert len(result["data"]) == len(result["periods"])
