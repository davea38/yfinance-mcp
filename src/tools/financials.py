"""Financial statements tools for Yahoo Finance MCP server."""

import yfinance as yf
from typing import Dict, Any
from utils import (
    validate_ticker_symbol,
    format_financial_statement,
    handle_yfinance_error
)


def get_income_statement(
    ticker: str,
    frequency: str = "quarterly"
) -> Dict[str, Any]:
    """
    Get income statement data for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        frequency: 'quarterly' for quarterly data or 'annual' for annual data

    Returns:
        Dictionary containing income statement with line items including:
        - Revenue (Total Revenue, Cost of Revenue)
        - Operating Expenses (R&D, SG&A)
        - Operating Income
        - Net Income
        - Earnings per Share (EPS)
        - EBITDA
    """
    try:
        ticker = validate_ticker_symbol(ticker)

        if frequency not in ['quarterly', 'annual']:
            return {
                "error": True,
                "message": "Frequency must be 'quarterly' or 'annual'",
                "ticker": ticker
            }

        stock = yf.Ticker(ticker)

        if frequency == 'quarterly':
            stmt = stock.quarterly_income_stmt
        else:
            stmt = stock.income_stmt

        if stmt is None or stmt.empty:
            return {
                "error": True,
                "message": f"No {frequency} income statement data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "frequency": frequency,
            **format_financial_statement(stmt, "income_statement")
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching {frequency} income statement")


def get_balance_sheet(
    ticker: str,
    frequency: str = "quarterly"
) -> Dict[str, Any]:
    """
    Get balance sheet data for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        frequency: 'quarterly' for quarterly data or 'annual' for annual data

    Returns:
        Dictionary containing balance sheet with line items including:
        - Assets (Current Assets, Total Assets, Cash, Inventory)
        - Liabilities (Current Liabilities, Long-term Debt, Total Liabilities)
        - Shareholders' Equity
        - Working Capital
    """
    try:
        ticker = validate_ticker_symbol(ticker)

        if frequency not in ['quarterly', 'annual']:
            return {
                "error": True,
                "message": "Frequency must be 'quarterly' or 'annual'",
                "ticker": ticker
            }

        stock = yf.Ticker(ticker)

        if frequency == 'quarterly':
            stmt = stock.quarterly_balance_sheet
        else:
            stmt = stock.balance_sheet

        if stmt is None or stmt.empty:
            return {
                "error": True,
                "message": f"No {frequency} balance sheet data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "frequency": frequency,
            **format_financial_statement(stmt, "balance_sheet")
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching {frequency} balance sheet")


def get_cash_flow(
    ticker: str,
    frequency: str = "quarterly"
) -> Dict[str, Any]:
    """
    Get cash flow statement data for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        frequency: 'quarterly' for quarterly data or 'annual' for annual data

    Returns:
        Dictionary containing cash flow statement with line items including:
        - Operating Cash Flow
        - Investing Cash Flow (CapEx, Acquisitions)
        - Financing Cash Flow (Dividends, Stock Buybacks, Debt)
        - Free Cash Flow
    """
    try:
        ticker = validate_ticker_symbol(ticker)

        if frequency not in ['quarterly', 'annual']:
            return {
                "error": True,
                "message": "Frequency must be 'quarterly' or 'annual'",
                "ticker": ticker
            }

        stock = yf.Ticker(ticker)

        if frequency == 'quarterly':
            stmt = stock.quarterly_cashflow
        else:
            stmt = stock.cashflow

        if stmt is None or stmt.empty:
            return {
                "error": True,
                "message": f"No {frequency} cash flow data available for {ticker}",
                "ticker": ticker
            }

        return {
            "ticker": ticker,
            "frequency": frequency,
            **format_financial_statement(stmt, "cash_flow")
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching {frequency} cash flow statement")


def get_financials(
    ticker: str,
    frequency: str = "quarterly"
) -> Dict[str, Any]:
    """
    Get all financial statements (income statement, balance sheet, and cash flow) in one call.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        frequency: 'quarterly' for quarterly data or 'annual' for annual data

    Returns:
        Dictionary containing all three financial statements:
        - Income statement
        - Balance sheet
        - Cash flow statement
    """
    try:
        ticker = validate_ticker_symbol(ticker)

        if frequency not in ['quarterly', 'annual']:
            return {
                "error": True,
                "message": "Frequency must be 'quarterly' or 'annual'",
                "ticker": ticker
            }

        # Get all three statements
        income = get_income_statement(ticker, frequency)
        balance = get_balance_sheet(ticker, frequency)
        cash_flow = get_cash_flow(ticker, frequency)

        return {
            "ticker": ticker,
            "frequency": frequency,
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": cash_flow
        }

    except Exception as e:
        return handle_yfinance_error(e, ticker, f"fetching {frequency} financial statements")
