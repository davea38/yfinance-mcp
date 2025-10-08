"""Options data tools for Yahoo Finance MCP server."""

import yfinance as yf
from typing import Dict, Any, Optional, List
from utils import (
    validate_ticker_symbol,
    format_dataframe_to_dict,
    handle_yfinance_error
)


def get_options_dates(ticker: str) -> Dict[str, Any]:
    """
    Get available options expiration dates for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')

    Returns:
        Dictionary containing list of available expiration dates for options
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)
        options_dates = stock.options

        if not options_dates or len(options_dates) == 0:
            return {
                "error": True,
                "message": f"No options data available for {ticker}. The stock may not have listed options.",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "expiration_dates": list(options_dates)
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, "fetching options dates")


def get_options_chain(
    ticker: str,
    expiration_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get full options chain (both calls and puts) for a specific expiration date.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        expiration_date: Options expiration date (YYYY-MM-DD format). If not provided,
                        uses the nearest expiration date.

    Returns:
        Dictionary containing options chain data:
        - Calls: strike prices, last price, bid, ask, volume, open interest, implied volatility
        - Puts: strike prices, last price, bid, ask, volume, open interest, implied volatility
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)

        # Get available expiration dates
        available_dates = stock.options

        if not available_dates or len(available_dates) == 0:
            return {
                "error": True,
                "message": f"No options data available for {ticker}",
                "ticker": ticker
            }

        # Use provided date or default to first available
        if expiration_date:
            if expiration_date not in available_dates:
                return {
                    "error": True,
                    "message": f"Expiration date {expiration_date} not found. Available dates: {', '.join(available_dates)}",
                    "ticker": ticker,
                    "available_dates": list(available_dates)
                }
            date_to_use = expiration_date
        else:
            date_to_use = available_dates[0]

        # Get options chain
        opt_chain = stock.option_chain(date_to_use)

        calls_data = format_dataframe_to_dict(opt_chain.calls) if not opt_chain.calls.empty else []
        puts_data = format_dataframe_to_dict(opt_chain.puts) if not opt_chain.puts.empty else []

        return {
            "ticker": ticker,
            "expiration_date": date_to_use,
            "calls": calls_data,
            "puts": puts_data
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching options chain (date={expiration_date})")


def get_calls(
    ticker: str,
    expiration_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get call options data for a specific expiration date.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        expiration_date: Options expiration date (YYYY-MM-DD format). If not provided,
                        uses the nearest expiration date.

    Returns:
        Dictionary containing call options data with:
        - Strike prices
        - Last price
        - Bid and ask
        - Volume
        - Open interest
        - Implied volatility
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)

        # Get available expiration dates
        available_dates = stock.options

        if not available_dates or len(available_dates) == 0:
            return {
                "error": True,
                "message": f"No options data available for {ticker}",
                "ticker": ticker
            }

        # Use provided date or default to first available
        if expiration_date:
            if expiration_date not in available_dates:
                return {
                    "error": True,
                    "message": f"Expiration date {expiration_date} not found. Available dates: {', '.join(available_dates)}",
                    "ticker": ticker,
                    "available_dates": list(available_dates)
                }
            date_to_use = expiration_date
        else:
            date_to_use = available_dates[0]

        # Get options chain
        opt_chain = stock.option_chain(date_to_use)

        calls_data = format_dataframe_to_dict(opt_chain.calls) if not opt_chain.calls.empty else []

        return {
            "ticker": ticker,
            "expiration_date": date_to_use,
            "calls": calls_data
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching call options (date={expiration_date})")


def get_puts(
    ticker: str,
    expiration_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get put options data for a specific expiration date.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        expiration_date: Options expiration date (YYYY-MM-DD format). If not provided,
                        uses the nearest expiration date.

    Returns:
        Dictionary containing put options data with:
        - Strike prices
        - Last price
        - Bid and ask
        - Volume
        - Open interest
        - Implied volatility
    """
    try:
        ticker = validate_ticker_symbol(ticker)
        stock = yf.Ticker(ticker)

        # Get available expiration dates
        available_dates = stock.options

        if not available_dates or len(available_dates) == 0:
            return {
                "error": True,
                "message": f"No options data available for {ticker}",
                "ticker": ticker
            }

        # Use provided date or default to first available
        if expiration_date:
            if expiration_date not in available_dates:
                return {
                    "error": True,
                    "message": f"Expiration date {expiration_date} not found. Available dates: {', '.join(available_dates)}",
                    "ticker": ticker,
                    "available_dates": list(available_dates)
                }
            date_to_use = expiration_date
        else:
            date_to_use = available_dates[0]

        # Get options chain
        opt_chain = stock.option_chain(date_to_use)

        puts_data = format_dataframe_to_dict(opt_chain.puts) if not opt_chain.puts.empty else []

        return {
            "ticker": ticker,
            "expiration_date": date_to_use,
            "puts": puts_data
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching put options (date={expiration_date})")
