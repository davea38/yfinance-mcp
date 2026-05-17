"""Unit tests for ``tools.bulk``.

Why these tests exist
---------------------

The two bulk tools provide multi-ticker operations and their *envelope shape*
and *stubbing strategy* differ from the single-ticker tools:

* ``download_multiple`` calls ``yf.download()`` (a module-level function, not
  ``yf.Ticker``), so the ``stub_ticker_factory`` fixture cannot help — we must
  monkeypatch ``bulk.yf.download`` directly.
* ``compare_stocks`` calls ``yf.Ticker`` per ticker, so we can use a custom
  lambda with ``monkeypatch.setattr(bulk.yf, "Ticker", ...)`` to hand back
  different ``info`` dicts per symbol, exercising the per-ticker error path
  without rebuilding the fixture machinery.

Key behavioural contracts protected here:

* Both tools validate that ``tickers`` is a non-empty list before touching
  yfinance — an empty list returns ``error: True`` immediately.
* ``download_multiple`` normalises tickers to uppercase and joins them with
  spaces before passing to ``yf.download``; swapping the separator or
  skipping normalisation would break multi-ticker requests silently.
* ``download_multiple`` returns ``error: True`` when ``yf.download`` hands
  back an empty DataFrame — the caller must never receive an empty ``data``
  list without an error flag.
* ``compare_stocks`` aggregates per-ticker errors into ``errors`` but still
  returns the successfully-fetched tickers in ``comparison``; a regression
  that short-circuits on first error would hide valid data.
* When *all* tickers fail in ``compare_stocks``, the response must carry
  top-level ``error: True`` — partial failure is fine, total failure is not.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tools import bulk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(dates: list[str] | None = None) -> pd.DataFrame:
    """Return a minimal OHLCV DataFrame shaped like ``yf.download`` output."""
    if dates is None:
        dates = ["2026-05-01", "2026-05-02", "2026-05-05"]
    idx = pd.DatetimeIndex(dates, name="Date")
    return pd.DataFrame(
        {
            "Open": [170.0, 171.0, 172.0][: len(dates)],
            "High": [175.0, 176.0, 177.0][: len(dates)],
            "Low": [168.0, 169.0, 170.0][: len(dates)],
            "Close": [174.0, 175.0, 176.0][: len(dates)],
            "Volume": [1_000_000, 1_100_000, 1_200_000][: len(dates)],
        },
        index=idx,
    )


def _make_info(
    ticker: str,
    *,
    current_price: float = 174.0,
    market_cap: int = 3_000_000_000_000,
) -> dict:
    """Build a minimal ``stock.info`` dict for ``compare_stocks`` tests."""
    return {
        "shortName": f"{ticker} Inc.",
        "currentPrice": current_price,
        "previousClose": current_price - 1.0,
        "marketCap": market_cap,
        "trailingPE": 28.5,
        "forwardPE": 24.0,
        "trailingEps": 6.11,
        "dividendYield": 0.005,
        "beta": 1.2,
        "fiftyTwoWeekHigh": 200.0,
        "fiftyTwoWeekLow": 130.0,
        "volume": 80_000_000,
        "averageVolume": 90_000_000,
        "sector": "Technology",
        "industry": "Consumer Electronics",
    }


# ---------------------------------------------------------------------------
# download_multiple
# ---------------------------------------------------------------------------


class TestDownloadMultiple:
    def test_happy_path_returns_envelope(self, monkeypatch):
        """Valid tickers: envelope has tickers/period/interval/data keys."""
        df = _make_ohlcv()
        monkeypatch.setattr(bulk.yf, "download", lambda *args, **kwargs: df)

        result = bulk.download_multiple(["aapl", "msft"], period="1mo", interval="1d")

        assert "error" not in result or result.get("error") is not True
        assert result["tickers"] == ["AAPL", "MSFT"]
        assert result["period"] == "1mo"
        assert result["interval"] == "1d"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == len(df)

    def test_tickers_normalised_to_uppercase(self, monkeypatch):
        """Lowercase tickers are uppercased before appearing in the result."""
        df = _make_ohlcv()
        monkeypatch.setattr(bulk.yf, "download", lambda *args, **kwargs: df)

        result = bulk.download_multiple(["aapl", "msft"])

        assert result["tickers"] == ["AAPL", "MSFT"]

    def test_tickers_str_passed_to_download_is_space_separated_and_uppercased(
        self, monkeypatch
    ):
        """yf.download must receive a single space-separated uppercase string."""
        captured: dict = {}

        def _fake_download(tickers_str, **kwargs):
            captured["tickers_str"] = tickers_str
            return _make_ohlcv()

        monkeypatch.setattr(bulk.yf, "download", _fake_download)
        bulk.download_multiple(["aapl", "msft", "googl"])

        assert captured["tickers_str"] == "AAPL MSFT GOOGL"

    def test_empty_tickers_list_returns_error(self, monkeypatch):
        """An empty list must return error immediately (before touching yfinance)."""
        called: list = []
        monkeypatch.setattr(
            bulk.yf,
            "download",
            lambda *a, **kw: called.append(True) or _make_ohlcv(),
        )

        result = bulk.download_multiple([])

        assert result["error"] is True
        assert not called  # yf.download must not be called

    def test_invalid_ticker_empty_string_returns_error(self, monkeypatch):
        """An empty string in the tickers list triggers a validation error."""
        called: list = []
        monkeypatch.setattr(
            bulk.yf,
            "download",
            lambda *a, **kw: called.append(True) or _make_ohlcv(),
        )

        result = bulk.download_multiple([""])

        assert result["error"] is True
        assert not called

    def test_invalid_period_returns_error(self, monkeypatch):
        """An unrecognised period string must return error before calling download."""
        called: list = []
        monkeypatch.setattr(
            bulk.yf,
            "download",
            lambda *a, **kw: called.append(True) or _make_ohlcv(),
        )

        result = bulk.download_multiple(["AAPL"], period="99y")

        assert result["error"] is True
        assert not called

    def test_invalid_interval_returns_error(self, monkeypatch):
        """An unrecognised interval string must return error before calling download."""
        called: list = []
        monkeypatch.setattr(
            bulk.yf,
            "download",
            lambda *a, **kw: called.append(True) or _make_ohlcv(),
        )

        result = bulk.download_multiple(["AAPL"], interval="10d")

        assert result["error"] is True
        assert not called

    def test_empty_dataframe_from_yf_returns_error(self, monkeypatch):
        """When yf.download returns an empty DataFrame the tool must error."""
        monkeypatch.setattr(
            bulk.yf, "download", lambda *args, **kwargs: pd.DataFrame()
        )

        result = bulk.download_multiple(["AAPL"])

        assert result["error"] is True
        assert "AAPL" in result.get("tickers", []) or "AAPL" in result.get("message", "")

    def test_download_kwargs_forwarded_correctly(self, monkeypatch):
        """yf.download must be called with the expected keyword arguments."""
        captured: dict = {}

        def _fake_download(tickers_str, **kwargs):
            captured.update(kwargs)
            return _make_ohlcv()

        monkeypatch.setattr(bulk.yf, "download", _fake_download)
        bulk.download_multiple(["AAPL"], period="3mo", interval="1wk")

        assert captured["period"] == "3mo"
        assert captured["interval"] == "1wk"
        assert captured["group_by"] == "ticker"
        assert captured["auto_adjust"] is True
        assert captured["prepost"] is False
        assert captured["threads"] is True
        assert captured["proxy"] is None

    def test_single_ticker_is_also_accepted(self, monkeypatch):
        """A list with one ticker is valid and returns the envelope correctly."""
        df = _make_ohlcv()
        monkeypatch.setattr(bulk.yf, "download", lambda *a, **kw: df)

        result = bulk.download_multiple(["MSFT"])

        assert result["tickers"] == ["MSFT"]
        assert isinstance(result["data"], list)


# ---------------------------------------------------------------------------
# compare_stocks
# ---------------------------------------------------------------------------


class TestCompareStocks:
    def test_happy_path_returns_comparison_list(self, monkeypatch):
        """Valid tickers each with info return a comparison list with all fields."""
        infos = {
            "AAPL": _make_info("AAPL", current_price=174.0, market_cap=3_000_000_000_000),
            "MSFT": _make_info("MSFT", current_price=420.0, market_cap=3_100_000_000_000),
        }
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: type(
                "StubTicker", (), {"info": infos[symbol]}
            )(),
        )

        result = bulk.compare_stocks(["aapl", "msft"])

        assert "error" not in result or result.get("error") is not True
        assert result["tickers"] == ["AAPL", "MSFT"]
        assert len(result["comparison"]) == 2

    def test_happy_path_expected_fields_present(self, monkeypatch):
        """Each entry in ``comparison`` must carry the 16 specified fields."""
        infos = {"AAPL": _make_info("AAPL")}
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: type("StubTicker", (), {"info": infos[symbol]})(),
        )

        result = bulk.compare_stocks(["AAPL"])
        entry = result["comparison"][0]

        expected_fields = {
            "ticker",
            "name",
            "current_price",
            "previous_close",
            "market_cap",
            "pe_ratio",
            "forward_pe",
            "eps",
            "dividend_yield",
            "beta",
            "52_week_high",
            "52_week_low",
            "volume",
            "average_volume",
            "sector",
            "industry",
        }
        assert expected_fields.issubset(set(entry.keys()))

    def test_ticker_field_in_comparison_is_uppercased(self, monkeypatch):
        """Normalisation: the ``ticker`` field in each entry must be uppercase."""
        infos = {"AAPL": _make_info("AAPL")}
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: type("StubTicker", (), {"info": infos[symbol]})(),
        )

        result = bulk.compare_stocks(["aapl"])
        assert result["comparison"][0]["ticker"] == "AAPL"

    def test_empty_tickers_list_returns_error(self, monkeypatch):
        """An empty list must return error immediately."""
        called: list = []
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: called.append(symbol),
        )

        result = bulk.compare_stocks([])

        assert result["error"] is True
        assert not called

    def test_invalid_ticker_empty_string_returns_error(self, monkeypatch):
        """An empty string in the list triggers validation error."""
        called: list = []
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: called.append(symbol),
        )

        result = bulk.compare_stocks([""])

        assert result["error"] is True
        assert not called

    def test_per_ticker_error_aggregated_into_errors(self, monkeypatch):
        """When one ticker raises, it lands in ``errors``; other tickers succeed."""
        infos = {"AAPL": _make_info("AAPL")}

        def _ctor(symbol):
            if symbol == "BADINPUT":
                raise RuntimeError("no data available")
            return type("StubTicker", (), {"info": infos[symbol]})()

        monkeypatch.setattr(bulk.yf, "Ticker", _ctor)

        result = bulk.compare_stocks(["AAPL", "BADINPUT"])

        # Successful ticker still appears in comparison
        assert len(result["comparison"]) == 1
        assert result["comparison"][0]["ticker"] == "AAPL"
        # Failing ticker's message is in errors
        assert "errors" in result
        assert any("BADINPUT" in e for e in result["errors"])

    def test_all_tickers_fail_returns_top_level_error(self, monkeypatch):
        """When every ticker errors, the response must carry ``error: True``."""

        def _ctor(symbol):
            raise RuntimeError(f"no data for {symbol}")

        monkeypatch.setattr(bulk.yf, "Ticker", _ctor)

        result = bulk.compare_stocks(["AAPL", "MSFT"])

        assert result["error"] is True
        assert "errors" in result

    def test_ticker_with_minimal_info_skipped_and_added_to_errors(self, monkeypatch):
        """A ticker that returns ``info`` with one or fewer keys is treated as
        no-data and recorded in ``errors`` rather than ``comparison``."""
        # yfinance returns {"trailingPegRatio": None} for unknown tickers
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: type("StubTicker", (), {"info": {"trailingPegRatio": None}})(),
        )

        result = bulk.compare_stocks(["FAKE"])

        assert result["error"] is True
        assert any("FAKE" in e for e in result.get("errors", []))

    def test_no_errors_key_when_all_succeed(self, monkeypatch):
        """When all tickers succeed, the response must not carry an ``errors`` key."""
        infos = {
            "AAPL": _make_info("AAPL"),
            "MSFT": _make_info("MSFT"),
        }
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: type("StubTicker", (), {"info": infos[symbol]})(),
        )

        result = bulk.compare_stocks(["AAPL", "MSFT"])

        assert "errors" not in result

    def test_tickers_key_present_in_successful_result(self, monkeypatch):
        """The envelope must carry the normalised ``tickers`` list."""
        infos = {"AAPL": _make_info("AAPL")}
        monkeypatch.setattr(
            bulk.yf,
            "Ticker",
            lambda symbol: type("StubTicker", (), {"info": infos[symbol]})(),
        )

        result = bulk.compare_stocks(["aapl"])

        assert result["tickers"] == ["AAPL"]
