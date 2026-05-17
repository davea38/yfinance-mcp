"""
Yahoo Finance MCP Server

This MCP server provides comprehensive financial data from Yahoo Finance including:
- Stock information and quotes
- Historical price data
- Financial statements
- Market analysis and analyst data
- Options data
- News and insights
"""

from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional

# Import tool implementations
from tools import stock_info, historical, financials, analysis, options, news, bulk, insiders

# Initialize FastMCP server
mcp = FastMCP("yahoo-finance", dependencies=["yfinance>=0.2.49"])


# Register stock information tools
@mcp.tool()
def get_stock_info(ticker: str) -> Dict[str, Any]:
    """Get comprehensive stock information including company details and key metrics."""
    return stock_info.get_stock_info(ticker)


@mcp.tool()
def get_current_price(ticker: str) -> Dict[str, Any]:
    """Get current/latest stock price and real-time quote data."""
    return stock_info.get_current_price(ticker)


@mcp.tool()
def get_market_cap(ticker: str) -> Dict[str, Any]:
    """Get market capitalization and valuation metrics for a stock."""
    return stock_info.get_market_cap(ticker)


@mcp.tool()
def get_major_holders(ticker: str) -> Dict[str, Any]:
    """Get major shareholders information including institutional and insider ownership."""
    return stock_info.get_major_holders(ticker)


@mcp.tool()
def get_institutional_holders(ticker: str) -> Dict[str, Any]:
    """Get detailed institutional holders information."""
    return stock_info.get_institutional_holders(ticker)


@mcp.tool()
def get_mutualfund_holders(ticker: str) -> Dict[str, Any]:
    """Get mutual fund holders information."""
    return stock_info.get_mutualfund_holders(ticker)


# Register historical data tools
@mcp.tool()
def get_historical_data(ticker: str, period: str = "1mo", interval: str = "1d") -> Dict[str, Any]:
    """Get historical price data for a stock. Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max. Interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo."""
    return historical.get_historical_data(ticker, period, interval)


@mcp.tool()
def get_dividends(ticker: str) -> Dict[str, Any]:
    """Get dividend payment history for a stock."""
    return historical.get_dividends(ticker)


@mcp.tool()
def get_splits(ticker: str) -> Dict[str, Any]:
    """Get stock split history."""
    return historical.get_splits(ticker)


@mcp.tool()
def get_actions(ticker: str) -> Dict[str, Any]:
    """Get all corporate actions including dividends and stock splits."""
    return historical.get_actions(ticker)


@mcp.tool()
def get_capital_gains(ticker: str) -> Dict[str, Any]:
    """Get capital gains distribution history (primarily for funds/ETFs)."""
    return historical.get_capital_gains(ticker)


# Register financial statement tools
@mcp.tool()
def get_income_statement(ticker: str, frequency: str = "quarterly") -> Dict[str, Any]:
    """Get income statement data. Frequency: 'quarterly' or 'annual'."""
    return financials.get_income_statement(ticker, frequency)


@mcp.tool()
def get_balance_sheet(ticker: str, frequency: str = "quarterly") -> Dict[str, Any]:
    """Get balance sheet data. Frequency: 'quarterly' or 'annual'."""
    return financials.get_balance_sheet(ticker, frequency)


@mcp.tool()
def get_cash_flow(ticker: str, frequency: str = "quarterly") -> Dict[str, Any]:
    """Get cash flow statement data. Frequency: 'quarterly' or 'annual'."""
    return financials.get_cash_flow(ticker, frequency)


@mcp.tool()
def get_financials(ticker: str, frequency: str = "quarterly") -> Dict[str, Any]:
    """Get all financial statements (income statement, balance sheet, and cash flow) in one call. Frequency: 'quarterly' or 'annual'."""
    return financials.get_financials(ticker, frequency)


# Register market analysis tools
@mcp.tool()
def get_analyst_recommendations(ticker: str) -> Dict[str, Any]:
    """Get analyst recommendations history (buy, sell, hold ratings)."""
    return analysis.get_analyst_recommendations(ticker)


@mcp.tool()
def get_analyst_price_targets(ticker: str) -> Dict[str, Any]:
    """Get analyst price targets and estimates."""
    return analysis.get_analyst_price_targets(ticker)


@mcp.tool()
def get_earnings(ticker: str) -> Dict[str, Any]:
    """Get earnings data including historical and estimated earnings."""
    return analysis.get_earnings(ticker)


@mcp.tool()
def get_earnings_dates(ticker: str) -> Dict[str, Any]:
    """Get upcoming and past earnings announcement dates."""
    return analysis.get_earnings_dates(ticker)


@mcp.tool()
def get_calendar(ticker: str) -> Dict[str, Any]:
    """Get company calendar events including earnings dates and dividend dates."""
    return analysis.get_calendar(ticker)


# Register options tools
@mcp.tool()
def get_options_dates(ticker: str) -> Dict[str, Any]:
    """Get available options expiration dates for a stock."""
    return options.get_options_dates(ticker)


@mcp.tool()
def get_options_chain(ticker: str, expiration_date: Optional[str] = None) -> Dict[str, Any]:
    """Get full options chain (both calls and puts) for a specific expiration date. If expiration_date is not provided, uses the nearest date."""
    return options.get_options_chain(ticker, expiration_date)


@mcp.tool()
def get_calls(ticker: str, expiration_date: Optional[str] = None) -> Dict[str, Any]:
    """Get call options data for a specific expiration date. If expiration_date is not provided, uses the nearest date."""
    return options.get_calls(ticker, expiration_date)


@mcp.tool()
def get_puts(ticker: str, expiration_date: Optional[str] = None) -> Dict[str, Any]:
    """Get put options data for a specific expiration date. If expiration_date is not provided, uses the nearest date."""
    return options.get_puts(ticker, expiration_date)


# Register news tools
@mcp.tool()
def get_news(ticker: str, limit: int = 10) -> Dict[str, Any]:
    """Get latest news articles for a stock. Limit specifies maximum number of articles to return."""
    return news.get_news(ticker, limit)


@mcp.tool()
def get_upgrades_downgrades(ticker: str) -> Dict[str, Any]:
    """Get analyst upgrades and downgrades history."""
    return news.get_upgrades_downgrades(ticker)


# Register insider activity tools
@mcp.tool()
def get_insider_transactions(ticker: str) -> Dict[str, Any]:
    """Get the raw log of recent insider buy/sell trades reported on Form 4."""
    return insiders.get_insider_transactions(ticker)


@mcp.tool()
def get_insider_purchases(ticker: str) -> Dict[str, Any]:
    """Get Yahoo's aggregate 6-month insider purchases/sales summary (totals, not individual trades)."""
    return insiders.get_insider_purchases(ticker)


@mcp.tool()
def get_insider_roster_holders(ticker: str) -> Dict[str, Any]:
    """Get the current snapshot of insiders and how many shares each holds directly."""
    return insiders.get_insider_roster_holders(ticker)


@mcp.tool()
def get_outsized_insider_transactions(
    ticker: str,
    lookback_days: int = 180,
    top_n: int = 10,
    sort: str = "proportional",
) -> Dict[str, Any]:
    """Rank recent insider trades by their proportional impact on each insider's stake; full exits are returned in a separate full_liquidations bucket. sort='proportional' (default) ranks by shares_transacted/insider_current_holdings; sort='value' ranks by raw dollar value."""
    return insiders.get_outsized_insider_transactions(ticker, lookback_days, top_n, sort)


# Register bulk operation tools
@mcp.tool()
def download_multiple(tickers: List[str], period: str = "1mo", interval: str = "1d") -> Dict[str, Any]:
    """Download historical data for multiple tickers at once. Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max. Interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo."""
    return bulk.download_multiple(tickers, period, interval)


@mcp.tool()
def compare_stocks(tickers: List[str]) -> Dict[str, Any]:
    """Compare key metrics across multiple stocks."""
    return bulk.compare_stocks(tickers)


def main():
    """Main entry point for the MCP server."""
    import sys

    # Check for HTTP mode via command line args
    if "--http" in sys.argv or "--sse" in sys.argv:
        import uvicorn

        port = 8080
        host = "0.0.0.0"
        # Check for custom port/host
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
            if arg == "--host" and i + 1 < len(sys.argv):
                host = sys.argv[i + 1]

        if "--http" in sys.argv:
            print(f"Starting Streamable HTTP server on http://{host}:{port}/mcp")
            app = mcp.streamable_http_app()
        else:
            print(f"Starting SSE server on http://{host}:{port}/sse")
            app = mcp.sse_app()

        uvicorn.run(app, host=host, port=port)
    else:
        # Default: stdio transport for local MCP clients
        mcp.run()


if __name__ == "__main__":
    main()
