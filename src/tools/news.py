"""News and insights tools for Yahoo Finance MCP server."""

import yfinance as yf
from typing import Dict, Any, List
from datetime import datetime
from utils import (
    validate_ticker_symbol,
    format_dataframe_to_dict,
    handle_yfinance_error
)


def get_news(ticker: str, limit: int = 10) -> Dict[str, Any]:
    """
    Get latest news articles for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        limit: Maximum number of news articles to return (default 10)

    Returns:
        Dictionary containing news articles with:
        - Title
        - Publisher
        - Link/URL
        - Published date
        - Type (e.g., article, video)
        - Thumbnail image
        - Summary/excerpt
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        news = stock.news

        if not news or len(news) == 0:
            return {
                "ticker": ticker,
                "message": f"No news articles available for {ticker}",
                "news": []
            }

        # Limit the number of articles
        news = news[:limit] if len(news) > limit else news

        # Format news articles
        formatted_news = []
        for article in news:
            formatted_article = {
                "title": article.get("title"),
                "publisher": article.get("publisher"),
                "link": article.get("link"),
                "published": datetime.fromtimestamp(article.get("providerPublishTime", 0)).isoformat()
                           if article.get("providerPublishTime") else None,
                "type": article.get("type"),
                "thumbnail": article.get("thumbnail"),
                "related_tickers": article.get("relatedTickers", [])
            }
            formatted_news.append(formatted_article)

        return {
            "ticker": ticker,
            "count": len(formatted_news),
            "news": formatted_news
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching news")


def get_upgrades_downgrades(ticker: str) -> Dict[str, Any]:
    """
    Get analyst upgrades and downgrades history.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing analyst rating changes with:
        - Date
        - Firm name
        - Action (Upgrade, Downgrade, Initiated, Reiterated)
        - Rating from and to (e.g., Hold -> Buy)
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        upgrades_downgrades = stock.upgrades_downgrades

        if upgrades_downgrades is None or upgrades_downgrades.empty:
            # Try getting recommendations as alternative
            recommendations = stock.recommendations

            if recommendations is not None and not recommendations.empty:
                return {
                    "ticker": ticker,
                    "message": "Using recommendations data as upgrades/downgrades not directly available",
                    "data": format_dataframe_to_dict(recommendations)
                }

            return {
                "error": True,
                "message": f"No upgrades/downgrades data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "data": format_dataframe_to_dict(upgrades_downgrades)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching upgrades/downgrades")
