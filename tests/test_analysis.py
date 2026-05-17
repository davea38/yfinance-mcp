"""Unit tests for ``tools.analysis``.

Why these tests exist
---------------------

The five analysis tools project yfinance data into structured dicts that
downstream LLM prompts depend on. Several contracts are easy to break silently:

* ``get_analyst_recommendations`` has a three-level fallback: primary
  ``recommendations`` DataFrame -> ``recommendations_summary`` -> error.
  Reordering or short-circuiting the fallback would cause the tool to
  return an error even when summary data is present.

* ``get_analyst_price_targets`` reads eight specific keys from ``stock.info``
  and exposes them flat. Renaming a key (e.g. ``target_mean_price`` ->
  ``mean_target``) would silently break callers.

* ``get_earnings`` gates success on *at least one* of ``quarterly_earnings``
  or ``annual_earnings`` being non-empty. ``earnings_forecasts`` and
  ``earnings_trend`` being populated must NOT cause a success return when
  both core frames are empty — that is the exact error contract.

* ``get_earnings_dates`` is a straightforward DataFrame pass-through; the
  test guards the shape and the empty-path error.

* ``get_calendar`` accepts three types from yfinance: a ``dict``, a
  ``DataFrame`` (has ``to_dict``), and ``None`` / empty-dict. The branch
  logic must not merge them. In particular the empty-dict path must error
  even though a non-empty dict returns success.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tools import analysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_recommendations_df():
    return pd.DataFrame(
        {
            "Firm": ["Goldman Sachs", "JP Morgan"],
            "To Grade": ["Buy", "Hold"],
            "From Grade": ["Hold", "Buy"],
            "Action": ["upgrade", "downgrade"],
        },
        index=pd.DatetimeIndex(
            ["2026-01-15", "2026-02-20"], name="Date"
        ),
    )


def _make_rec_summary_df():
    return pd.DataFrame(
        {
            "period": ["0m", "-1m"],
            "strongBuy": [10, 8],
            "buy": [15, 14],
            "hold": [5, 6],
            "sell": [1, 2],
            "strongSell": [0, 0],
        }
    )


def _make_quarterly_earnings_df():
    return pd.DataFrame(
        {"Revenue": [100_000_000, 120_000_000], "Earnings": [20_000_000, 25_000_000]},
        index=pd.Index(["2025Q1", "2025Q2"], name="Quarter"),
    )


def _make_annual_earnings_df():
    return pd.DataFrame(
        {"Revenue": [400_000_000, 450_000_000], "Earnings": [80_000_000, 90_000_000]},
        index=pd.Index([2024, 2025], name="Year"),
    )


def _make_earnings_dates_df():
    return pd.DataFrame(
        {
            "EPS Estimate": [1.20, 1.35],
            "Reported EPS": [1.22, None],
            "Surprise(%)": [1.67, None],
        },
        index=pd.DatetimeIndex(
            ["2026-01-28", "2026-04-29"], name="Earnings Date"
        ),
    )


def _make_calendar_df():
    return pd.DataFrame(
        {
            "Earnings Date": [pd.Timestamp("2026-07-30")],
            "Earnings Average": [1.50],
            "Earnings Low": [1.30],
            "Earnings High": [1.70],
        }
    )


# ---------------------------------------------------------------------------
# get_analyst_recommendations
# ---------------------------------------------------------------------------


class TestGetAnalystRecommendations:
    def test_happy_path_primary_recommendations(self, stub_ticker_factory):
        """Primary path: ``stock.recommendations`` is populated."""
        df = _make_recommendations_df()
        stub_ticker_factory(
            analysis,
            {
                "recommendations": df,
                "info": {},
                "recommendations_summary": pd.DataFrame(),
            },
        )
        result = analysis.get_analyst_recommendations("AAPL")

        assert result["ticker"] == "AAPL"
        assert "recommendations" in result
        assert len(result["recommendations"]) == 2
        first = result["recommendations"][0]
        assert "Firm" in first
        assert "To Grade" in first

    def test_fallback_to_recommendations_summary(self, stub_ticker_factory):
        """When ``recommendations`` is empty, fall back to ``recommendations_summary``."""
        stub_ticker_factory(
            analysis,
            {
                "recommendations": pd.DataFrame(),
                "info": {"longName": "Apple Inc."},
                "recommendations_summary": _make_rec_summary_df(),
            },
        )
        result = analysis.get_analyst_recommendations("AAPL")

        assert result["ticker"] == "AAPL"
        assert "recommendations_summary" in result
        assert "recommendations" not in result
        assert len(result["recommendations_summary"]) == 2

    def test_full_empty_returns_error(self, stub_ticker_factory):
        """When both ``recommendations`` and ``recommendations_summary`` are empty, error."""
        stub_ticker_factory(
            analysis,
            {
                "recommendations": pd.DataFrame(),
                "info": {},
                "recommendations_summary": pd.DataFrame(),
            },
        )
        result = analysis.get_analyst_recommendations("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_recommendations_none_also_triggers_fallback(self, stub_ticker_factory):
        """``None`` for ``recommendations`` is treated the same as an empty DataFrame."""
        stub_ticker_factory(
            analysis,
            {
                "recommendations": None,
                "info": {},
                "recommendations_summary": _make_rec_summary_df(),
            },
        )
        result = analysis.get_analyst_recommendations("AAPL")

        assert "recommendations_summary" in result

    def test_exception_returns_error_structure(self, stub_ticker_factory):
        stub_ticker_factory(analysis, {"recommendations": None, "info": RuntimeError("boom")})
        # Accessing ``info`` raises; that exception must be caught.
        # We patch via a raising property by replacing the yf.Ticker constructor.
        import tools.analysis as _mod

        original = _mod.yf.Ticker

        class _Boom:
            def __init__(self, _):
                pass

            @property
            def recommendations(self):
                return None

            @property
            def info(self):
                raise RuntimeError("network failure")

        _mod.yf.Ticker = _Boom
        try:
            result = analysis.get_analyst_recommendations("AAPL")
        finally:
            _mod.yf.Ticker = original

        assert result["error"] is True
        assert "network failure" in result["message"]


# ---------------------------------------------------------------------------
# get_analyst_price_targets
# ---------------------------------------------------------------------------


class TestGetAnalystPriceTargets:
    _FULL_INFO = {
        "currentPrice": 189.50,
        "targetMeanPrice": 210.00,
        "targetHighPrice": 240.00,
        "targetLowPrice": 175.00,
        "targetMedianPrice": 209.00,
        "numberOfAnalystOpinions": 35,
        "recommendationMean": 1.8,
        "recommendationKey": "buy",
    }

    def test_happy_path_all_fields_present(self, stub_ticker_factory):
        stub_ticker_factory(analysis, {"info": self._FULL_INFO})
        result = analysis.get_analyst_price_targets("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["current_price"] == 189.50
        assert result["target_mean_price"] == 210.00
        assert result["target_high_price"] == 240.00
        assert result["target_low_price"] == 175.00
        assert result["target_median_price"] == 209.00
        assert result["number_of_analyst_opinions"] == 35
        assert result["recommendation_mean"] == 1.8
        assert result["recommendation_key"] == "buy"

    def test_empty_info_returns_error(self, stub_ticker_factory):
        """When ``info`` is empty or has only 1 key, return error."""
        stub_ticker_factory(analysis, {"info": {}})
        result = analysis.get_analyst_price_targets("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_info_with_single_key_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(analysis, {"info": {"trailingPegRatio": None}})
        result = analysis.get_analyst_price_targets("AAPL")
        assert result["error"] is True

    def test_missing_keys_return_none_not_keyerror(self, stub_ticker_factory):
        """Info populated but specific price-target keys absent -> None values, no crash."""
        stub_ticker_factory(analysis, {"info": {"longName": "Apple Inc.", "sector": "Tech"}})
        result = analysis.get_analyst_price_targets("AAPL")

        # len(info) > 1, so we get a result rather than an error
        assert "error" not in result or result.get("error") is not True
        assert result.get("target_mean_price") is None
        assert result.get("current_price") is None

    def test_exception_returns_error_structure(self, stub_ticker_factory):
        import tools.analysis as _mod

        original = _mod.yf.Ticker

        class _Boom:
            def __init__(self, _):
                pass

            @property
            def info(self):
                raise ConnectionError("timeout")

        _mod.yf.Ticker = _Boom
        try:
            result = analysis.get_analyst_price_targets("AAPL")
        finally:
            _mod.yf.Ticker = original

        assert result["error"] is True
        assert "timeout" in result["message"]


# ---------------------------------------------------------------------------
# get_earnings
# ---------------------------------------------------------------------------


class TestGetEarnings:
    def test_happy_path_both_frames_populated(self, stub_ticker_factory):
        """Both quarterly and annual earnings present -> full result bundle."""
        stub_ticker_factory(
            analysis,
            {
                "quarterly_earnings": _make_quarterly_earnings_df(),
                "earnings": _make_annual_earnings_df(),
                "earnings_forecasts": pd.DataFrame(),
                "earnings_trend": pd.DataFrame(),
            },
        )
        result = analysis.get_earnings("AAPL")

        assert result["ticker"] == "AAPL"
        assert len(result["quarterly_earnings"]) == 2
        assert len(result["annual_earnings"]) == 2
        # Optional keys absent when frames empty
        assert "earnings_forecasts" not in result
        assert "earnings_trend" not in result

    def test_quarterly_only_succeeds(self, stub_ticker_factory):
        stub_ticker_factory(
            analysis,
            {
                "quarterly_earnings": _make_quarterly_earnings_df(),
                "earnings": pd.DataFrame(),
                "earnings_forecasts": pd.DataFrame(),
                "earnings_trend": pd.DataFrame(),
            },
        )
        result = analysis.get_earnings("AAPL")

        assert "error" not in result or result.get("error") is not True
        assert len(result["quarterly_earnings"]) == 2
        assert result["annual_earnings"] == []

    def test_annual_only_succeeds(self, stub_ticker_factory):
        stub_ticker_factory(
            analysis,
            {
                "quarterly_earnings": pd.DataFrame(),
                "earnings": _make_annual_earnings_df(),
                "earnings_forecasts": pd.DataFrame(),
                "earnings_trend": pd.DataFrame(),
            },
        )
        result = analysis.get_earnings("AAPL")

        assert "error" not in result or result.get("error") is not True
        assert len(result["annual_earnings"]) == 2
        assert result["quarterly_earnings"] == []

    def test_forecasts_and_trend_included_when_populated(self, stub_ticker_factory):
        """Optional frames appear in the result only when non-empty."""
        forecasts_df = pd.DataFrame({"EPS Estimate": [1.5, 1.6]})
        trend_df = pd.DataFrame({"period": ["0q", "+1q"], "growth": [0.05, 0.08]})
        stub_ticker_factory(
            analysis,
            {
                "quarterly_earnings": _make_quarterly_earnings_df(),
                "earnings": pd.DataFrame(),
                "earnings_forecasts": forecasts_df,
                "earnings_trend": trend_df,
            },
        )
        result = analysis.get_earnings("AAPL")

        assert "earnings_forecasts" in result
        assert "earnings_trend" in result

    def test_both_empty_with_forecasts_and_trend_returns_error(self, stub_ticker_factory):
        """Contract: error if BOTH quarterly AND annual are empty,
        even when forecasts/trend are populated."""
        stub_ticker_factory(
            analysis,
            {
                "quarterly_earnings": pd.DataFrame(),
                "earnings": pd.DataFrame(),
                "earnings_forecasts": pd.DataFrame({"EPS Estimate": [1.5]}),
                "earnings_trend": pd.DataFrame({"period": ["0q"]}),
            },
        )
        result = analysis.get_earnings("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_both_none_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(
            analysis,
            {
                "quarterly_earnings": None,
                "earnings": None,
                "earnings_forecasts": None,
                "earnings_trend": None,
            },
        )
        result = analysis.get_earnings("AAPL")
        assert result["error"] is True

    def test_exception_returns_error_structure(self, stub_ticker_factory):
        import tools.analysis as _mod

        original = _mod.yf.Ticker

        class _Boom:
            def __init__(self, _):
                pass

            @property
            def quarterly_earnings(self):
                raise RuntimeError("rate limit")

        _mod.yf.Ticker = _Boom
        try:
            result = analysis.get_earnings("AAPL")
        finally:
            _mod.yf.Ticker = original

        assert result["error"] is True
        assert "rate limit" in result["message"]


# ---------------------------------------------------------------------------
# get_earnings_dates
# ---------------------------------------------------------------------------


class TestGetEarningsDates:
    def test_happy_path_shape(self, stub_ticker_factory):
        df = _make_earnings_dates_df()
        stub_ticker_factory(analysis, {"earnings_dates": df})
        result = analysis.get_earnings_dates("AAPL")

        assert result["ticker"] == "AAPL"
        assert "earnings_dates" in result
        assert len(result["earnings_dates"]) == 2
        first = result["earnings_dates"][0]
        assert "EPS Estimate" in first

    def test_empty_df_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(analysis, {"earnings_dates": pd.DataFrame()})
        result = analysis.get_earnings_dates("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_none_returns_error(self, stub_ticker_factory):
        stub_ticker_factory(analysis, {"earnings_dates": None})
        result = analysis.get_earnings_dates("AAPL")
        assert result["error"] is True

    def test_exception_returns_error_structure(self, stub_ticker_factory):
        import tools.analysis as _mod

        original = _mod.yf.Ticker

        class _Boom:
            def __init__(self, _):
                pass

            @property
            def earnings_dates(self):
                raise RuntimeError("timeout")

        _mod.yf.Ticker = _Boom
        try:
            result = analysis.get_earnings_dates("AAPL")
        finally:
            _mod.yf.Ticker = original

        assert result["error"] is True


# ---------------------------------------------------------------------------
# get_calendar
# ---------------------------------------------------------------------------


class TestGetCalendar:
    def test_happy_path_dict_calendar(self, stub_ticker_factory):
        """Non-empty dict path: returned as-is under ``calendar`` key."""
        cal_dict = {
            "Earnings Date": ["2026-07-30", "2026-07-31"],
            "Earnings Average": 1.50,
            "Earnings Low": 1.30,
            "Earnings High": 1.70,
            "Ex-Dividend Date": "2026-08-09",
            "Dividend Date": "2026-08-13",
        }
        stub_ticker_factory(analysis, {"calendar": cal_dict})
        result = analysis.get_calendar("AAPL")

        assert result["ticker"] == "AAPL"
        assert "calendar" in result
        # dict path returns the dict as-is, so keys are preserved
        assert result["calendar"] == cal_dict

    def test_happy_path_dataframe_calendar(self, stub_ticker_factory):
        """DataFrame path: ``format_dataframe_to_dict`` is called (``to_dict`` present)."""
        df = _make_calendar_df()
        stub_ticker_factory(analysis, {"calendar": df})
        result = analysis.get_calendar("AAPL")

        assert result["ticker"] == "AAPL"
        assert "calendar" in result
        # format_dataframe_to_dict converts to list-of-dicts
        assert isinstance(result["calendar"], list)
        assert len(result["calendar"]) == 1
        assert "Earnings Date" in result["calendar"][0]

    def test_none_calendar_returns_error(self, stub_ticker_factory):
        """``None`` triggers the empty-branch error."""
        stub_ticker_factory(analysis, {"calendar": None})
        result = analysis.get_calendar("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_empty_dict_calendar_returns_error(self, stub_ticker_factory):
        """Empty dict ``{}`` also triggers the error — distinct from non-empty dict."""
        stub_ticker_factory(analysis, {"calendar": {}})
        result = analysis.get_calendar("AAPL")

        assert result["error"] is True
        assert result["ticker"] == "AAPL"

    def test_exception_returns_error_structure(self, stub_ticker_factory):
        import tools.analysis as _mod

        original = _mod.yf.Ticker

        class _Boom:
            def __init__(self, _):
                pass

            @property
            def calendar(self):
                raise RuntimeError("yahoo is down")

        _mod.yf.Ticker = _Boom
        try:
            result = analysis.get_calendar("AAPL")
        finally:
            _mod.yf.Ticker = original

        assert result["error"] is True
        assert "yahoo is down" in result["message"]
