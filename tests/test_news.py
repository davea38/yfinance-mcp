"""Unit tests for ``tools.news``.

Why these tests exist
---------------------

The two news tools project yfinance data into normalised shapes that LLM
prompts depend on:

* ``get_news`` converts a raw list of dicts (keyed with camelCase yfinance
  field names) into a snake_case-normalised dict, converts the unix-epoch
  ``providerPublishTime`` to ISO 8601, honours the ``limit`` parameter, and
  returns a message-style (not error-style) response when no news is available.

* ``get_upgrades_downgrades`` has a two-level fallback: first
  ``stock.upgrades_downgrades``, then ``stock.recommendations``.  Each path
  returns a *different response shape* that is documented in the ADR, so
  accidental merging or silent fallback would break downstream consumers.

These tests guard against:
- Timestamp conversion regressions (epoch int -> ISO string).
- Off-by-one errors in ``limit`` slicing.
- The empty-news path returning ``message`` instead of ``error: True``.
- The recommendations fallback carrying a ``message`` key that explains the
  detour, so the LLM can flag the data provenance.
- The both-empty path returning ``error: True``.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tools import news


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNIX_TS = 1_700_000_000  # 2023-11-14T22:13:20 (UTC)


def _make_article(
    title: str = "Test headline",
    publisher: str = "Reuters",
    link: str = "https://example.com/article",
    provider_publish_time: int = _UNIX_TS,
    article_type: str = "STORY",
    thumbnail: dict | None = None,
    related_tickers: list | None = None,
) -> dict:
    """Build a minimal article dict matching the yfinance ``stock.news`` shape."""
    return {
        "title": title,
        "publisher": publisher,
        "link": link,
        "providerPublishTime": provider_publish_time,
        "type": article_type,
        "thumbnail": thumbnail,
        "relatedTickers": related_tickers if related_tickers is not None else [],
    }


def _make_upgrades_df(rows=1) -> pd.DataFrame:
    """Build a minimal upgrades/downgrades DataFrame."""
    data = {
        "Firm": ["Goldman Sachs"] * rows,
        "ToGrade": ["Buy"] * rows,
        "FromGrade": ["Hold"] * rows,
        "Action": ["upgrade"] * rows,
    }
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2026-05-10")] * rows, name="GradeDate"
    )
    return pd.DataFrame(data, index=idx)


def _make_recommendations_df() -> pd.DataFrame:
    """Build a minimal recommendations DataFrame."""
    data = {
        "period": ["0m"],
        "strongBuy": [5],
        "buy": [15],
        "hold": [8],
        "sell": [2],
        "strongSell": [0],
    }
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# get_news — happy path
# ---------------------------------------------------------------------------


def test_get_news_happy_path_shape(stub_ticker_factory):
    """Happy path: returns ticker, count, and a news list."""
    articles = [_make_article(title=f"Headline {i}") for i in range(3)]
    stub_ticker_factory(news, {"news": articles})

    result = news.get_news("aapl")

    assert result["ticker"] == "AAPL"
    assert result["count"] == 3
    assert len(result["news"]) == 3
    assert "error" not in result


def test_get_news_count_matches_news_list_length(stub_ticker_factory):
    """``count`` must always equal ``len(news)`` in the response."""
    articles = [_make_article() for _ in range(5)]
    stub_ticker_factory(news, {"news": articles})

    result = news.get_news("MSFT")

    assert result["count"] == len(result["news"])


def test_get_news_normalised_fields(stub_ticker_factory):
    """Each article dict must carry the normalised keys, not yfinance camelCase."""
    thumbnail = {"resolutions": []}
    article = _make_article(
        title="Big news",
        publisher="Bloomberg",
        link="https://bloomberg.com/x",
        provider_publish_time=_UNIX_TS,
        article_type="STORY",
        thumbnail=thumbnail,
        related_tickers=["AAPL", "MSFT"],
    )
    stub_ticker_factory(news, {"news": [article]})

    result = news.get_news("AAPL")
    item = result["news"][0]

    assert item["title"] == "Big news"
    assert item["publisher"] == "Bloomberg"
    assert item["link"] == "https://bloomberg.com/x"
    assert item["type"] == "STORY"
    assert item["thumbnail"] == thumbnail
    assert item["related_tickers"] == ["AAPL", "MSFT"]
    # camelCase originals must NOT leak through
    assert "providerPublishTime" not in item
    assert "relatedTickers" not in item


def test_get_news_timestamp_converted_to_iso(stub_ticker_factory):
    """``providerPublishTime`` (unix epoch int) must become an ISO 8601 string."""
    articles = [_make_article(provider_publish_time=_UNIX_TS)]
    stub_ticker_factory(news, {"news": articles})

    result = news.get_news("AAPL")
    published = result["news"][0]["published"]

    assert isinstance(published, str)
    # Must be parseable as an ISO timestamp
    from datetime import datetime
    dt = datetime.fromisoformat(published)
    assert dt.year == 2023


def test_get_news_limit_truncates_list(stub_ticker_factory):
    """Giving 5 articles and requesting limit=3 must return exactly 3."""
    articles = [_make_article(title=f"Article {i}") for i in range(5)]
    stub_ticker_factory(news, {"news": articles})

    result = news.get_news("AAPL", limit=3)

    assert result["count"] == 3
    assert len(result["news"]) == 3


def test_get_news_limit_larger_than_available(stub_ticker_factory):
    """Limit larger than the available list must not error — return all."""
    articles = [_make_article() for _ in range(4)]
    stub_ticker_factory(news, {"news": articles})

    result = news.get_news("AAPL", limit=20)

    assert result["count"] == 4
    assert len(result["news"]) == 4


# ---------------------------------------------------------------------------
# get_news — empty / error path
# ---------------------------------------------------------------------------


def test_get_news_empty_list_returns_message_dict(stub_ticker_factory):
    """Empty news returns message-style response (not error: True)."""
    stub_ticker_factory(news, {"news": []})

    result = news.get_news("AAPL")

    assert "ticker" in result
    assert "message" in result
    assert result["news"] == []
    assert result.get("error") is not True


def test_get_news_none_returns_message_dict(stub_ticker_factory):
    """``stock.news = None`` also returns message-style response."""
    stub_ticker_factory(news, {"news": None})

    result = news.get_news("AAPL")

    assert "ticker" in result
    assert "message" in result
    assert result["news"] == []
    assert result.get("error") is not True


def test_get_news_exception_returns_error(stub_ticker_factory, monkeypatch):
    """An unexpected exception from yfinance surfaces as error: True."""
    def _boom(symbol: str):
        raise RuntimeError("network failure")

    monkeypatch.setattr(news.yf, "Ticker", _boom)

    result = news.get_news("AAPL")

    assert result.get("error") is True


# ---------------------------------------------------------------------------
# get_upgrades_downgrades — happy path (primary data)
# ---------------------------------------------------------------------------


def test_get_upgrades_downgrades_happy_path_shape(stub_ticker_factory):
    """Primary path: upgrades_downgrades DataFrame present -> returns data key."""
    df = _make_upgrades_df(rows=2)
    stub_ticker_factory(news, {"upgrades_downgrades": df, "recommendations": pd.DataFrame()})

    result = news.get_upgrades_downgrades("AAPL")

    assert result["ticker"] == "AAPL"
    assert "data" in result
    assert isinstance(result["data"], list)
    assert len(result["data"]) == 2
    assert "error" not in result


def test_get_upgrades_downgrades_normalises_ticker(stub_ticker_factory):
    """Ticker is normalised to upper-case by validate_ticker_symbol."""
    df = _make_upgrades_df()
    stub_ticker_factory(news, {"upgrades_downgrades": df, "recommendations": pd.DataFrame()})

    result = news.get_upgrades_downgrades("aapl")

    assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# get_upgrades_downgrades — fallback to recommendations
# ---------------------------------------------------------------------------


def test_get_upgrades_downgrades_fallback_recommendations(stub_ticker_factory):
    """Empty upgrades_downgrades but non-empty recommendations -> fallback path."""
    rec_df = _make_recommendations_df()
    stub_ticker_factory(
        news,
        {
            "upgrades_downgrades": pd.DataFrame(),
            "recommendations": rec_df,
        },
    )

    result = news.get_upgrades_downgrades("AAPL")

    assert result["ticker"] == "AAPL"
    assert "data" in result
    assert "message" in result
    assert "error" not in result or result.get("error") is not True


def test_get_upgrades_downgrades_fallback_message_explains_provenance(stub_ticker_factory):
    """Fallback response must carry a message telling callers it used recommendations."""
    rec_df = _make_recommendations_df()
    stub_ticker_factory(
        news,
        {
            "upgrades_downgrades": pd.DataFrame(),
            "recommendations": rec_df,
        },
    )

    result = news.get_upgrades_downgrades("MSFT")

    msg = result.get("message", "")
    # The message should mention recommendations (case-insensitive)
    assert "recommendation" in msg.lower()


def test_get_upgrades_downgrades_fallback_none_upgrades(stub_ticker_factory):
    """``upgrades_downgrades = None`` triggers the fallback correctly."""
    rec_df = _make_recommendations_df()
    stub_ticker_factory(
        news,
        {
            "upgrades_downgrades": None,
            "recommendations": rec_df,
        },
    )

    result = news.get_upgrades_downgrades("AAPL")

    assert "data" in result
    assert "message" in result


# ---------------------------------------------------------------------------
# get_upgrades_downgrades — both-empty error path
# ---------------------------------------------------------------------------


def test_get_upgrades_downgrades_both_empty_returns_error(stub_ticker_factory):
    """Both DataFrames empty/None -> error: True."""
    stub_ticker_factory(
        news,
        {
            "upgrades_downgrades": pd.DataFrame(),
            "recommendations": pd.DataFrame(),
        },
    )

    result = news.get_upgrades_downgrades("AAPL")

    assert result["error"] is True
    assert result["ticker"] == "AAPL"


def test_get_upgrades_downgrades_both_none_returns_error(stub_ticker_factory):
    """Both properties None -> error: True."""
    stub_ticker_factory(
        news,
        {
            "upgrades_downgrades": None,
            "recommendations": None,
        },
    )

    result = news.get_upgrades_downgrades("AAPL")

    assert result["error"] is True


def test_get_upgrades_downgrades_exception_returns_error(monkeypatch):
    """An unexpected exception surfaces as error: True."""
    def _boom(symbol: str):
        raise RuntimeError("bad request")

    monkeypatch.setattr(news.yf, "Ticker", _boom)

    result = news.get_upgrades_downgrades("AAPL")

    assert result.get("error") is True
