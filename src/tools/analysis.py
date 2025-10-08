"""Market analysis tools for Yahoo Finance MCP server."""

import yfinance as yf
from typing import Dict, Any
from utils import (
    validate_ticker_symbol,
    format_dataframe_to_dict,
    format_series_to_dict,
    handle_yfinance_error
)


def get_analyst_recommendations(ticker: str) -> Dict[str, Any]:
    """
    Get analyst recommendations history (buy, sell, hold ratings).

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing analyst recommendation history with:
        - Date
        - Firm name
        - Rating (Strong Buy, Buy, Hold, Sell, Strong Sell)
        - Previous rating (if available)
        - Action (upgrade, downgrade, initiated, reiterated)
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        recommendations = stock.recommendations

        if recommendations is None or recommendations.empty:
            # Try alternative method
            info = stock.info
            rec_trend = stock.recommendations_summary

            if rec_trend is not None and not rec_trend.empty:
                return {
                    "ticker": ticker,
                    "recommendations_summary": format_dataframe_to_dict(rec_trend)
                }

            return {
                "error": True,
                "message": f"No analyst recommendations data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "recommendations": format_dataframe_to_dict(recommendations)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching analyst recommendations")


def get_analyst_price_targets(ticker: str) -> Dict[str, Any]:
    """
    Get analyst price targets and estimates.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing analyst price target information:
        - Current price
        - Target mean price
        - Target high price
        - Target low price
        - Target median price
        - Number of analysts
        - Recommendation (e.g., 'Buy', 'Hold')
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or len(info) <= 1:
            return {
                "error": True,
                "message": f"No data found for ticker {ticker}",
                "ticker": ticker
            }

        price_targets = {
            "ticker": ticker,
            "current_price": info.get("currentPrice"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            "recommendation_mean": info.get("recommendationMean"),
            "recommendation_key": info.get("recommendationKey")
        }

        return price_targets

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching analyst price targets")


def get_earnings(ticker: str) -> Dict[str, Any]:
    """
    Get earnings data including historical and estimated earnings.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing earnings information:
        - Historical quarterly earnings
        - Historical annual earnings
        - Earnings estimates
        - Revenue estimates
        - EPS trends
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)

        # Get quarterly and annual earnings
        quarterly_earnings = stock.quarterly_earnings
        annual_earnings = stock.earnings

        result = {
            "ticker": ticker
        }

        if quarterly_earnings is not None and not quarterly_earnings.empty:
            result["quarterly_earnings"] = format_dataframe_to_dict(quarterly_earnings)
        else:
            result["quarterly_earnings"] = []

        if annual_earnings is not None and not annual_earnings.empty:
            result["annual_earnings"] = format_dataframe_to_dict(annual_earnings)
        else:
            result["annual_earnings"] = []

        # Get earnings estimates
        earnings_forecasts = stock.earnings_forecasts
        if earnings_forecasts is not None and not earnings_forecasts.empty:
            result["earnings_forecasts"] = format_dataframe_to_dict(earnings_forecasts)

        # Get earnings trend
        earnings_trend = stock.earnings_trend
        if earnings_trend is not None and not earnings_trend.empty:
            result["earnings_trend"] = format_dataframe_to_dict(earnings_trend)

        if not result.get("quarterly_earnings") and not result.get("annual_earnings"):
            return {
                "error": True,
                "message": f"No earnings data available for {ticker}",
                "ticker": ticker
            }

        return result

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching earnings data")


def get_earnings_dates(ticker: str) -> Dict[str, Any]:
    """
    Get upcoming and past earnings announcement dates.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing earnings dates with:
        - Earnings date
        - EPS estimate
        - Reported EPS
        - Surprise percentage
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        earnings_dates = stock.earnings_dates

        if earnings_dates is None or earnings_dates.empty:
            return {
                "error": True,
                "message": f"No earnings dates available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "earnings_dates": format_dataframe_to_dict(earnings_dates)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching earnings dates")


def get_calendar(ticker: str) -> Dict[str, Any]:
    """
    Get company calendar events including earnings dates and dividend dates.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing calendar information:
        - Earnings dates
        - Dividend dates
        - Ex-dividend date
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        calendar = stock.calendar

        if calendar is None or (isinstance(calendar, dict) and len(calendar) == 0):
            return {
                "error": True,
                "message": f"No calendar data available for {ticker}",
                "ticker": ticker
            }

        # Calendar can be a DataFrame or dict
        if hasattr(calendar, 'to_dict'):
            calendar_data = format_dataframe_to_dict(calendar)
        elif isinstance(calendar, dict):
            calendar_data = calendar
        else:
            calendar_data = format_series_to_dict(calendar)

        return {
            "ticker": ticker,
            "calendar": calendar_data
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching calendar data")
