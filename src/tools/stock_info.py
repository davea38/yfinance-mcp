"""Stock information tools for Yahoo Finance MCP server."""

import yfinance as yf
from typing import Dict, Any, Optional
from utils import (
    validate_ticker_symbol,
    format_dataframe_to_dict,
    format_series_to_dict,
    handle_yfinance_error
)


def get_stock_info(ticker: str) -> Dict[str, Any]:
    """
    Get comprehensive stock information including company details and key metrics.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing stock information including:
        - Basic info (name, sector, industry, description)
        - Price data (current price, previous close, 52-week high/low)
        - Valuation metrics (market cap, P/E ratio, EPS)
        - Trading data (volume, average volume, beta)
        - Dividend information
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or len(info) <= 1:
            return {
                "error": True,
                "message": f"No data found for ticker {ticker}. The symbol may be invalid.",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "info": info
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching stock info")


def get_current_price(ticker: str) -> Dict[str, Any]:
    """
    Get current/latest stock price and real-time quote data.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing current price data including:
        - Current price
        - Open, high, low for the day
        - Previous close
        - Volume
        - Bid/ask prices
        - Market cap
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

        price_data = {
            "ticker": ticker,
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "previous_close": info.get("previousClose") or info.get("regularMarketPreviousClose"),
            "open": info.get("open") or info.get("regularMarketOpen"),
            "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "bid": info.get("bid"),
            "ask": info.get("ask"),
            "bid_size": info.get("bidSize"),
            "ask_size": info.get("askSize"),
            "market_cap": info.get("marketCap")
        }

        return price_data

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching current price")


def get_market_cap(ticker: str) -> Dict[str, Any]:
    """
    Get market capitalization and valuation metrics for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing valuation metrics including:
        - Market cap
        - Enterprise value
        - Price-to-earnings ratio
        - Price-to-book ratio
        - Price-to-sales ratio
        - PEG ratio
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

        valuation_data = {
            "ticker": ticker,
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "enterprise_to_revenue": info.get("enterpriseToRevenue"),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda")
        }

        return valuation_data

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching market cap data")


def get_major_holders(ticker: str) -> Dict[str, Any]:
    """
    Get major shareholders information including institutional and insider ownership.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing major holders data with ownership percentages
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        major_holders = stock.major_holders

        if major_holders is None or major_holders.empty:
            return {
                "error": True,
                "message": f"No major holders data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "major_holders": format_dataframe_to_dict(major_holders)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching major holders")


def get_institutional_holders(ticker: str) -> Dict[str, Any]:
    """
    Get detailed institutional holders information.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing list of institutional holders with:
        - Holder name
        - Shares held
        - Date reported
        - Percentage of shares outstanding
        - Value of holdings
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        institutional = stock.institutional_holders

        if institutional is None or institutional.empty:
            return {
                "error": True,
                "message": f"No institutional holders data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "institutional_holders": format_dataframe_to_dict(institutional)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching institutional holders")


def get_mutualfund_holders(ticker: str) -> Dict[str, Any]:
    """
    Get mutual fund holders information.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing list of mutual fund holders with:
        - Holder name
        - Shares held
        - Date reported
        - Percentage of shares outstanding
        - Value of holdings
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        mutualfund = stock.mutualfund_holders

        if mutualfund is None or mutualfund.empty:
            return {
                "error": True,
                "message": f"No mutual fund holders data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "mutualfund_holders": format_dataframe_to_dict(mutualfund)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching mutual fund holders")
