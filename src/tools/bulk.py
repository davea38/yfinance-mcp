"""Bulk operations tools for Yahoo Finance MCP server."""

import yfinance as yf
from typing import Dict, Any, List
from utils import (
    validate_ticker_symbol,
    validate_period,
    validate_interval,
    format_dataframe_to_dict,
    handle_yfinance_error
)


def download_multiple(
    tickers: List[str],
    period: str = "1mo",
    interval: str = "1d"
) -> Dict[str, Any]:
    """
    Download historical data for multiple tickers at once.

    Args:
        tickers: List of stock ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
        period: Data period - valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
                Default is '1mo' (1 month)
        interval: Data interval - valid values: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
                  Default is '1d' (daily)

    Returns:
        Dictionary containing historical data for all tickers
    """
    try:
        # Validate tickers
        if not tickers or not isinstance(tickers, list):
            return {
                "error": True,
                "message": "Tickers must be a non-empty list of ticker symbols"
            }

        validated_tickers = []
        for ticker in tickers:
            try:
                validated_tickers.append(validate_ticker_symbol(ticker))
            except ValueError as e:
                return {
                    "error": True,
                    "message": f"Invalid ticker '{ticker}': {str(e)}"
                }

        period = validate_period(period)
        interval = validate_interval(interval)

        # Download data for all tickers
        tickers_str = " ".join(validated_tickers)
        data = yf.download(
            tickers_str,
            period=period,
            interval=interval,
            group_by='ticker',
            auto_adjust=True,
            prepost=False,
            threads=True,
            proxy=None
        )

        if data is None or data.empty:
            return {
                "error": True,
                "message": f"No data found for tickers: {', '.join(validated_tickers)}",
                "tickers": validated_tickers
            }

        # Format the data
        result = {
            "tickers": validated_tickers,
            "period": period,
            "interval": interval,
            "data": format_dataframe_to_dict(data)
        }

        return result

    except Exception as e:
        return {
            "error": True,
            "message": f"Error downloading data for multiple tickers: {str(e)}",
            "tickers": tickers if isinstance(tickers, list) else []
        }


def compare_stocks(tickers: List[str]) -> Dict[str, Any]:
    """
    Compare key metrics across multiple stocks.

    Args:
        tickers: List of stock ticker symbols to compare (e.g., ['AAPL', 'MSFT', 'GOOGL'])

    Returns:
        Dictionary containing comparative metrics for all tickers including:
        - Current price
        - Market cap
        - P/E ratio
        - EPS
        - Dividend yield
        - 52-week high/low
        - Beta
        - Volume
    """
    try:
        # Validate tickers
        if not tickers or not isinstance(tickers, list):
            return {
                "error": True,
                "message": "Tickers must be a non-empty list of ticker symbols"
            }

        validated_tickers = []
        for ticker in tickers:
            try:
                validated_tickers.append(validate_ticker_symbol(ticker))
            except ValueError as e:
                return {
                    "error": True,
                    "message": f"Invalid ticker '{ticker}': {str(e)}"
                }

        # Collect data for each ticker
        comparison_data = []
        errors = []

        for ticker in validated_tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info

                if not info or len(info) <= 1:
                    errors.append(f"No data found for {ticker}")
                    continue

                ticker_data = {
                    "ticker": ticker,
                    "name": info.get("shortName") or info.get("longName"),
                    "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                    "previous_close": info.get("previousClose"),
                    "market_cap": info.get("marketCap"),
                    "pe_ratio": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "eps": info.get("trailingEps"),
                    "dividend_yield": info.get("dividendYield"),
                    "beta": info.get("beta"),
                    "52_week_high": info.get("fiftyTwoWeekHigh"),
                    "52_week_low": info.get("fiftyTwoWeekLow"),
                    "volume": info.get("volume"),
                    "average_volume": info.get("averageVolume"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry")
                }

                comparison_data.append(ticker_data)

            except Exception as e:
                errors.append(f"Error fetching data for {ticker}: {str(e)}")

        if not comparison_data:
            return {
                "error": True,
                "message": "Could not fetch data for any of the provided tickers",
                "tickers": validated_tickers,
                "errors": errors
            }

        result = {
            "tickers": validated_tickers,
            "comparison": comparison_data
        }

        if errors:
            result["errors"] = errors

        return result

    except Exception as e:
        return {
            "error": True,
            "message": f"Error comparing stocks: {str(e)}",
            "tickers": tickers if isinstance(tickers, list) else []
        }
