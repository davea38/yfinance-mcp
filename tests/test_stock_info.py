"""Unit tests for ``tools.stock_info``.

Why these tests exist
---------------------

The six stock-info tools form the first layer of the yfinance-mcp surface —
anything that breaks here silently breaks every downstream LLM workflow that
asks "what is the current price / market cap / ownership of X?".

Specific regressions these tests guard against:

* ``get_stock_info`` must return ``{"ticker", "info"}`` on success and must
  gate on ``len(info) <= 1`` (not on falsiness alone) — a one-key dict
  (Yahoo's "symbol-not-found" sentinel) must still surface as an error.
* ``get_current_price`` projects a fixed set of keys from ``stock.info`` and
  falls back from ``currentPrice`` to ``regularMarketPrice`` (and similarly
  for other ``regularMarket*`` alternatives). A refactor that drops the
  fallback or renames an output key would break LLM tool callers that read
  ``current_price`` directly.
* ``get_market_cap`` projects enterprise value, both PE flavours, PEG,
  price-to-book, and price-to-sales from ``stock.info``. Accidental removal
  of any projected key is a silent contract break.
* ``get_major_holders``, ``get_institutional_holders``, and
  ``get_mutualfund_holders`` all follow the same pass-through shape:
  ``{"ticker", "<bucket>": [...]}`` on success, ``{"error": True, ...}`` on
  empty/None. Column renames in the yfinance DataFrame would silently survive
  without these tests.
* ``validate_ticker_symbol`` must normalise lowercase input to uppercase —
  callers should not have to pre-normalise.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tools import stock_info


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rich_info() -> dict:
    """Return a representative yfinance ``info`` dict with many keys."""
    return {
        "symbol": "AAPL",
        "shortName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "longBusinessSummary": "Apple designs iPhones.",
        "currentPrice": 189.50,
        "previousClose": 187.25,
        "open": 188.00,
        "dayHigh": 191.00,
        "dayLow": 187.50,
        "volume": 55_000_000,
        "bid": 189.49,
        "ask": 189.51,
        "bidSize": 100,
        "askSize": 200,
        "marketCap": 2_950_000_000_000,
        "enterpriseValue": 2_920_000_000_000,
        "trailingPE": 30.5,
        "forwardPE": 27.8,
        "pegRatio": 2.3,
        "priceToBook": 45.1,
        "priceToSalesTrailing12Months": 7.8,
        "enterpriseToRevenue": 7.5,
        "enterpriseToEbitda": 22.1,
        "trailingEps": 6.20,
        "beta": 1.25,
        "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 164.08,
        "averageVolume": 58_000_000,
        "dividendYield": 0.005,
    }


def _make_holders_df(kind: str = "major") -> pd.DataFrame:
    if kind == "major":
        return pd.DataFrame(
            {
                "Value": ["10.21%", "72.15%", "0.06%", "73.15%"],
                "Breakdown": [
                    "% of Shares Held by All Insider",
                    "% of Shares Held by Institutions",
                    "% of Float Held by Insiders",
                    "% of Float Held by Institutions",
                ],
            }
        )
    if kind == "institutional":
        return pd.DataFrame(
            {
                "Holder": ["Vanguard Group Inc", "BlackRock Inc"],
                "Shares": [1_270_000_000, 1_020_000_000],
                "Date Reported": [pd.Timestamp("2026-03-31")] * 2,
                "% Out": [8.27, 6.63],
                "Value": [241_000_000_000, 193_000_000_000],
            }
        )
    # mutualfund
    return pd.DataFrame(
        {
            "Holder": ["Vanguard Total Stock Mkt Idx", "Fidelity 500 Index Fund"],
            "Shares": [450_000_000, 320_000_000],
            "Date Reported": [pd.Timestamp("2026-03-31")] * 2,
            "% Out": [2.93, 2.08],
            "Value": [85_000_000_000, 60_000_000_000],
        }
    )


# ---------------------------------------------------------------------------
# get_stock_info
# ---------------------------------------------------------------------------


def test_get_stock_info_happy_path(stub_ticker_factory):
    """Rich info dict -> returns ticker + info; ticker is normalised."""
    stub_ticker_factory(stock_info, {"info": _rich_info()})

    result = stock_info.get_stock_info("aapl")  # lowercase — tests normalisation

    assert result["ticker"] == "AAPL"
    assert "info" in result
    assert result["info"]["shortName"] == "Apple Inc."
    assert "error" not in result


def test_get_stock_info_empty_info_returns_error(stub_ticker_factory):
    """Empty dict triggers the ``len(info) <= 1`` guard -> error: True."""
    stub_ticker_factory(stock_info, {"info": {}})

    result = stock_info.get_stock_info("AAPL")

    assert result["error"] is True
    assert result["ticker"] == "AAPL"
    assert "message" in result


def test_get_stock_info_one_key_sentinel_returns_error(stub_ticker_factory):
    """A one-key dict (Yahoo's not-found sentinel) must also be an error."""
    stub_ticker_factory(stock_info, {"info": {"trailingPegRatio": None}})

    result = stock_info.get_stock_info("INVALID")

    assert result["error"] is True


# ---------------------------------------------------------------------------
# get_current_price
# ---------------------------------------------------------------------------


def test_get_current_price_happy_path_primary_keys(stub_ticker_factory):
    """Primary price keys (currentPrice, dayHigh …) are projected correctly."""
    stub_ticker_factory(stock_info, {"info": _rich_info()})

    result = stock_info.get_current_price("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["current_price"] == 189.50
    assert result["previous_close"] == 187.25
    assert result["open"] == 188.00
    assert result["day_high"] == 191.00
    assert result["day_low"] == 187.50
    assert result["volume"] == 55_000_000
    assert result["bid"] == 189.49
    assert result["ask"] == 189.51
    assert result["bid_size"] == 100
    assert result["ask_size"] == 200
    assert result["market_cap"] == 2_950_000_000_000
    assert "error" not in result


def test_get_current_price_fallback_to_regularmarket_keys(stub_ticker_factory):
    """When primary keys are absent, regularMarket* alternatives are used."""
    info = _rich_info()
    # Remove primary keys so the fallback path is exercised.
    del info["currentPrice"]
    del info["previousClose"]
    del info["open"]
    del info["dayHigh"]
    del info["dayLow"]
    del info["volume"]
    # Inject the regularMarket alternatives.
    info["regularMarketPrice"] = 190.00
    info["regularMarketPreviousClose"] = 188.00
    info["regularMarketOpen"] = 189.00
    info["regularMarketDayHigh"] = 192.00
    info["regularMarketDayLow"] = 188.50
    info["regularMarketVolume"] = 54_000_000

    stub_ticker_factory(stock_info, {"info": info})

    result = stock_info.get_current_price("AAPL")

    assert result["current_price"] == 190.00
    assert result["previous_close"] == 188.00
    assert result["open"] == 189.00
    assert result["day_high"] == 192.00
    assert result["day_low"] == 188.50
    assert result["volume"] == 54_000_000


def test_get_current_price_empty_info_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"info": {}})

    result = stock_info.get_current_price("AAPL")

    assert result["error"] is True
    assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# get_market_cap
# ---------------------------------------------------------------------------


def test_get_market_cap_happy_path(stub_ticker_factory):
    """All valuation keys are projected; both PE flavours and PEG are present."""
    stub_ticker_factory(stock_info, {"info": _rich_info()})

    result = stock_info.get_market_cap("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["market_cap"] == 2_950_000_000_000
    assert result["enterprise_value"] == 2_920_000_000_000
    assert result["trailing_pe"] == 30.5
    assert result["forward_pe"] == 27.8
    assert result["pe_ratio"] == 30.5          # trailing_pe is truthy so wins
    assert result["peg_ratio"] == 2.3
    assert result["price_to_book"] == 45.1
    assert result["price_to_sales"] == 7.8
    assert result["enterprise_to_revenue"] == 7.5
    assert result["enterprise_to_ebitda"] == 22.1
    assert "error" not in result


def test_get_market_cap_pe_fallback_to_forward(stub_ticker_factory):
    """When trailingPE is absent, pe_ratio falls back to forwardPE."""
    info = _rich_info()
    del info["trailingPE"]

    stub_ticker_factory(stock_info, {"info": info})

    result = stock_info.get_market_cap("AAPL")

    assert result["trailing_pe"] is None
    assert result["pe_ratio"] == info["forwardPE"]


def test_get_market_cap_empty_info_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"info": {}})

    result = stock_info.get_market_cap("AAPL")

    assert result["error"] is True
    assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# get_major_holders
# ---------------------------------------------------------------------------


def test_get_major_holders_happy_path(stub_ticker_factory):
    """Holders DataFrame is serialised; result carries ticker + bucket."""
    df = _make_holders_df("major")
    stub_ticker_factory(stock_info, {"major_holders": df})

    result = stock_info.get_major_holders("AAPL")

    assert result["ticker"] == "AAPL"
    assert "major_holders" in result
    assert len(result["major_holders"]) == len(df)
    # Shape check: first row must have the columns we put in.
    first = result["major_holders"][0]
    assert "Value" in first or "Breakdown" in first
    assert "error" not in result


def test_get_major_holders_empty_df_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"major_holders": pd.DataFrame()})

    result = stock_info.get_major_holders("AAPL")

    assert result["error"] is True
    assert result["ticker"] == "AAPL"


def test_get_major_holders_none_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"major_holders": None})

    result = stock_info.get_major_holders("AAPL")

    assert result["error"] is True


# ---------------------------------------------------------------------------
# get_institutional_holders
# ---------------------------------------------------------------------------


def test_get_institutional_holders_happy_path(stub_ticker_factory):
    """Institutional holders DataFrame is serialised correctly."""
    df = _make_holders_df("institutional")
    stub_ticker_factory(stock_info, {"institutional_holders": df})

    result = stock_info.get_institutional_holders("AAPL")

    assert result["ticker"] == "AAPL"
    assert "institutional_holders" in result
    assert len(result["institutional_holders"]) == len(df)
    first = result["institutional_holders"][0]
    assert "Holder" in first
    assert "Shares" in first
    assert "error" not in result


def test_get_institutional_holders_empty_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"institutional_holders": pd.DataFrame()})

    result = stock_info.get_institutional_holders("AAPL")

    assert result["error"] is True
    assert result["ticker"] == "AAPL"


def test_get_institutional_holders_none_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"institutional_holders": None})

    result = stock_info.get_institutional_holders("AAPL")

    assert result["error"] is True


# ---------------------------------------------------------------------------
# get_mutualfund_holders
# ---------------------------------------------------------------------------


def test_get_mutualfund_holders_happy_path(stub_ticker_factory):
    """Mutual-fund holders DataFrame is serialised correctly."""
    df = _make_holders_df("mutualfund")
    stub_ticker_factory(stock_info, {"mutualfund_holders": df})

    result = stock_info.get_mutualfund_holders("AAPL")

    assert result["ticker"] == "AAPL"
    assert "mutualfund_holders" in result
    assert len(result["mutualfund_holders"]) == len(df)
    first = result["mutualfund_holders"][0]
    assert "Holder" in first
    assert "Shares" in first
    assert "error" not in result


def test_get_mutualfund_holders_empty_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"mutualfund_holders": pd.DataFrame()})

    result = stock_info.get_mutualfund_holders("AAPL")

    assert result["error"] is True
    assert result["ticker"] == "AAPL"


def test_get_mutualfund_holders_none_returns_error(stub_ticker_factory):
    stub_ticker_factory(stock_info, {"mutualfund_holders": None})

    result = stock_info.get_mutualfund_holders("AAPL")

    assert result["error"] is True


# ---------------------------------------------------------------------------
# Ticker normalisation (cross-cutting)
# ---------------------------------------------------------------------------


def test_ticker_normalised_to_uppercase_across_tools(stub_ticker_factory):
    """validate_ticker_symbol must upper-case lowercase input for all six tools."""
    # Use get_stock_info as a representative; the shared validate_ticker_symbol
    # is called identically in every tool so one smoke test suffices.
    stub_ticker_factory(stock_info, {"info": _rich_info()})
    result = stock_info.get_stock_info("aapl")
    assert result["ticker"] == "AAPL"
