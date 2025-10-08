"""Utility functions for Yahoo Finance MCP server."""

import pandas as pd
from typing import Any, Optional, Dict, List, Union
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_dataframe_to_dict(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert a pandas DataFrame to a list of dictionaries with proper type handling.

    Args:
        df: The DataFrame to convert

    Returns:
        List of dictionaries representing each row
    """
    if df is None or df.empty:
        return []

    # Reset index to include it in the output if it's meaningful
    if df.index.name or not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()

    # Convert to dict and handle NaN/None values
    result = df.to_dict(orient='records')

    # Clean up the data
    for record in result:
        for key, value in list(record.items()):
            # Convert pandas timestamps to ISO format strings
            if isinstance(value, pd.Timestamp):
                record[key] = value.isoformat()
            # Convert numpy/pandas NA to None
            elif pd.isna(value):
                record[key] = None
            # Convert numpy types to Python types
            elif hasattr(value, 'item'):
                try:
                    record[key] = value.item()
                except (ValueError, AttributeError):
                    record[key] = str(value)

    return result


def format_series_to_dict(series: pd.Series) -> Dict[str, Any]:
    """
    Convert a pandas Series to a dictionary with proper type handling.

    Args:
        series: The Series to convert

    Returns:
        Dictionary representation of the Series
    """
    if series is None or series.empty:
        return {}

    result = series.to_dict()

    # Clean up the data
    for key, value in list(result.items()):
        # Convert pandas timestamps to ISO format strings
        if isinstance(value, pd.Timestamp):
            result[key] = value.isoformat()
        # Convert numpy/pandas NA to None
        elif pd.isna(value):
            result[key] = None
        # Convert numpy types to Python types
        elif hasattr(value, 'item'):
            try:
                result[key] = value.item()
            except (ValueError, AttributeError):
                result[key] = str(value)

    return result


def safe_get_ticker_info(ticker_obj, attribute: str, default: Any = None) -> Any:
    """
    Safely get an attribute from a yfinance Ticker object.

    Args:
        ticker_obj: The yfinance Ticker object
        attribute: The attribute name to retrieve
        default: Default value if attribute doesn't exist or raises an error

    Returns:
        The attribute value or default
    """
    try:
        value = getattr(ticker_obj, attribute, default)
        if value is None:
            return default
        return value
    except Exception as e:
        logger.warning(f"Error getting {attribute}: {str(e)}")
        return default


def validate_ticker_symbol(symbol: str) -> str:
    """
    Validate and normalize a ticker symbol.

    Args:
        symbol: The ticker symbol to validate

    Returns:
        Normalized ticker symbol

    Raises:
        ValueError: If the symbol is invalid
    """
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Ticker symbol must be a non-empty string")

    # Remove whitespace and convert to uppercase
    symbol = symbol.strip().upper()

    if len(symbol) == 0:
        raise ValueError("Ticker symbol cannot be empty")

    return symbol


def validate_period(period: str) -> str:
    """
    Validate a period string for historical data.

    Valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max

    Args:
        period: The period string to validate

    Returns:
        The validated period string

    Raises:
        ValueError: If the period is invalid
    """
    valid_periods = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max']

    if period not in valid_periods:
        raise ValueError(f"Invalid period. Must be one of: {', '.join(valid_periods)}")

    return period


def validate_interval(interval: str) -> str:
    """
    Validate an interval string for historical data.

    Valid intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo

    Args:
        interval: The interval string to validate

    Returns:
        The validated interval string

    Raises:
        ValueError: If the interval is invalid
    """
    valid_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']

    if interval not in valid_intervals:
        raise ValueError(f"Invalid interval. Must be one of: {', '.join(valid_intervals)}")

    return interval


def handle_yfinance_error(e: Exception, ticker: str, operation: str) -> Dict[str, Any]:
    """
    Handle yfinance errors and return a structured error response.

    Args:
        e: The exception that occurred
        ticker: The ticker symbol being processed
        operation: The operation that failed

    Returns:
        Error response dictionary
    """
    error_msg = f"Error {operation} for {ticker}: {str(e)}"
    logger.error(error_msg)

    return {
        "error": True,
        "message": error_msg,
        "ticker": ticker,
        "operation": operation
    }


def format_financial_statement(df: pd.DataFrame, statement_type: str) -> Dict[str, Any]:
    """
    Format a financial statement DataFrame into a structured dictionary.

    Args:
        df: The financial statement DataFrame
        statement_type: Type of statement (income_statement, balance_sheet, cash_flow)

    Returns:
        Formatted financial statement dictionary
    """
    if df is None or df.empty:
        return {
            "statement_type": statement_type,
            "data": [],
            "periods": []
        }

    # Transpose so dates are rows and line items are columns
    df_transposed = df.T

    return {
        "statement_type": statement_type,
        "periods": [col.isoformat() if isinstance(col, pd.Timestamp) else str(col)
                   for col in df_transposed.index],
        "data": format_dataframe_to_dict(df_transposed)
    }
