"""Historical data tools for Yahoo Finance MCP server."""

import yfinance as yf
from typing import Dict, Any, Optional
from utils import (
    validate_ticker_symbol,
    validate_period,
    validate_interval,
    format_dataframe_to_dict,
    handle_yfinance_error
)


def get_historical_data(
    ticker: str,
    period: str = "1mo",
    interval: str = "1d"
) -> Dict[str, Any]:
    """
    Get historical price data for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        period: Data period - valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
                Default is '1mo' (1 month)
        interval: Data interval - valid values: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
                  Default is '1d' (daily)

    Returns:
        Dictionary containing historical price data with:
        - Date/timestamp
        - Open, High, Low, Close prices
        - Volume
        - Adjusted Close (dividends and splits adjusted)
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        period = validate_period(period)
        interval = validate_interval(interval)

        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)

        if hist is None or hist.empty:
            return {
                "error": True,
                "message": f"No historical data available for {ticker} with period={period}, interval={interval}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "data": format_dataframe_to_dict(hist)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching historical data (period={period}, interval={interval})")


def get_dividends(ticker: str) -> Dict[str, Any]:
    """
    Get dividend payment history for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing dividend payment history with dates and amounts
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        dividends = stock.dividends

        if dividends is None or dividends.empty:
            return {
                "ticker": ticker,
                "message": f"No dividend data available for {ticker}",
                "data": []
            }

        # Convert Series to list of dicts with date and amount
        dividend_data = [
            {
                "date": date.isoformat(),
                "amount": float(amount)
            }
            for date, amount in dividends.items()
        ]

        return {
            "ticker": ticker,
            "data": dividend_data
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching dividends")


def get_splits(ticker: str) -> Dict[str, Any]:
    """
    Get stock split history.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing stock split history with dates and split ratios
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        splits = stock.splits

        if splits is None or splits.empty:
            return {
                "ticker": ticker,
                "message": f"No stock split data available for {ticker}",
                "data": []
            }

        # Convert Series to list of dicts with date and split ratio
        split_data = [
            {
                "date": date.isoformat(),
                "split_ratio": str(amount)
            }
            for date, amount in splits.items()
        ]

        return {
            "ticker": ticker,
            "data": split_data
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching stock splits")


def get_actions(ticker: str) -> Dict[str, Any]:
    """
    Get all corporate actions including dividends and stock splits.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing all corporate actions with dates, types, and values
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        actions = stock.actions

        if actions is None or actions.empty:
            return {
                "ticker": ticker,
                "message": f"No corporate actions data available for {ticker}",
                "data": []
            }

        return {
            "ticker": ticker,
            "data": format_dataframe_to_dict(actions)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching corporate actions")


def get_capital_gains(ticker: str) -> Dict[str, Any]:
    """
    Get capital gains distribution history (primarily for funds/ETFs).

    Args:
        ticker: Fund/ETF ticker symbol (e.g., 'SPY', 'QQQ')

    Returns:
        Dictionary containing capital gains distribution history with dates and amounts
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        capital_gains = stock.capital_gains

        if capital_gains is None or capital_gains.empty:
            return {
                "ticker": ticker,
                "message": f"No capital gains data available for {ticker}. This is typically only available for funds/ETFs.",
                "data": []
            }

        # Convert Series to list of dicts with date and amount
        gains_data = [
            {
                "date": date.isoformat(),
                "amount": float(amount)
            }
            for date, amount in capital_gains.items()
        ]

        return {
            "ticker": ticker,
            "data": gains_data
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching capital gains")
