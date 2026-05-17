# Yahoo Finance MCP Server

A comprehensive Model Context Protocol (MCP) server that provides access to Yahoo Finance data including stock prices, financial statements, market analysis, options data, and more.

## Features

This MCP server provides **36 tools** organized into 9 categories:
<details>
<summary><b>Stock Information (6 Tools)</b></summary>
<ul>
  <li>
    <strong>get_stock_info</strong> – Comprehensive company information and key metrics
  </li>
  <li>
    <strong>get_current_price</strong> – Real-time stock price and quote data
  </li>
  <li>
    <strong>get_market_cap</strong> – Market capitalization and valuation metrics
  </li>
  <li>
    <strong>get_major_holders</strong> – Major shareholders information
  </li>
  <li>
    <strong>get_institutional_holders</strong> – Detailed institutional holder data
  </li>
  <li>
    <strong>get_mutualfund_holders</strong> – Mutual fund holder information
  </li>
</ul>
</details>


<details>
<summary><b>Historical Data (5 Tools)</b></summary>
<ul>
  <li>
    <strong>get_historical_data</strong> – Historical price data with flexible periods/intervals
  </li>
  <li>
    <strong>get_dividends</strong> – Dividend payment history
  </li>
  <li>
    <strong>get_splits</strong> – Stock split history
  </li>
  <li>
    <strong>get_actions</strong> – Combined dividends and splits
  </li>
  <li>
    <strong>get_capital_gains</strong> – Capital gains distribution (for funds/ETFs)
  </li>
</ul>
</details>

<details>
<summary><b>Financial Statements (4 Tools)</b></summary>
<ul>
  <li>
    <strong>get_income_statement</strong> – Income statement (quarterly/annual)
  </li>
  <li>
    <strong>get_balance_sheet</strong> – Balance sheet (quarterly/annual)
  </li>
  <li>
    <strong>get_cash_flow</strong> – Cash flow statement (quarterly/annual)
  </li>
  <li>
    <strong>get_financials</strong> – All financial statements combined
  </li>
</ul>
</details>

<details>
<summary><b>Market Analysis (5 Tools)</b></summary>
<ul>
  <li>
    <strong>get_analyst_recommendations</strong> – Analyst buy/sell/hold recommendations
  </li>
  <li>
    <strong>get_analyst_price_targets</strong> – Analyst price target estimates
  </li>
  <li>
    <strong>get_earnings</strong> – Historical and estimated earnings data
  </li>
  <li>
    <strong>get_earnings_dates</strong> – Upcoming earnings calendar
  </li>
  <li>
    <strong>get_calendar</strong> – Company events calendar
  </li>
</ul>
</details>

<details>
<summary><b>Options & Derivatives (4 Tools)</b></summary>
<ul>
  <li>
    <strong>get_options_dates</strong> – Available option expiration dates
  </li>
  <li>
    <strong>get_options_chain</strong> – Full options chain for a date
  </li>
  <li>
    <strong>get_calls</strong> – Call options data
  </li>
  <li>
    <strong>get_puts</strong> – Put options data
  </li>
</ul>
</details>

<details>
<summary><b>Insider Activity (4 Tools)</b></summary>
<ul>
  <li>
    <strong>get_insider_transactions</strong> – Raw per-trade log of Form 4 insider buys/sells
  </li>
  <li>
    <strong>get_insider_purchases</strong> – Yahoo's aggregate 6-month purchases/sales summary
  </li>
  <li>
    <strong>get_insider_roster_holders</strong> – Current snapshot of insider holdings
  </li>
  <li>
    <strong>get_outsized_insider_transactions</strong> – Trades ranked by their proportional impact on each insider's stake; full exits surface in a separate <code>full_liquidations</code> bucket
  </li>
</ul>
</details>

<details>
<summary><b>Market Calendars (4 Tools)</b></summary>
<ul>
  <li>
    <strong>get_market_earnings_calendar</strong> – Market-wide upcoming earnings releases; optional <code>market_cap</code> floor, <code>filter_most_active</code>, <code>limit</code> (Yahoo cap 100)
  </li>
  <li>
    <strong>get_market_ipo_calendar</strong> – Market-wide upcoming IPO filings/listings
  </li>
  <li>
    <strong>get_market_splits_calendar</strong> – Market-wide upcoming stock-split events
  </li>
  <li>
    <strong>get_market_economic_calendar</strong> – Market-wide scheduled macro releases (CPI, jobs, central-bank events)
  </li>
</ul>
<p>
These four <strong>market-wide</strong> tools are deliberately separate from the per-ticker
<code>get_calendar</code> above — Yahoo overloads the word "calendar" with two
unrelated APIs (one company's events vs. a market-wide stream). The <code>market_</code>
prefix signals the scope split to LLM clients; see the ADR at
<code>.scratch/market-vs-company-calendar/0001-market-vs-company-calendar.md</code>.
</p>
</details>

<details>
<summary><b>News & Insights (2 Tools)</b></summary>
<ul>
  <li>
    <strong>get_news</strong> – Latest news articles with summaries
  </li>
  <li>
    <strong>get_upgrades_downgrades</strong> – Analyst rating changes
  </li>
</ul>
</details>

<details>
<summary><b>Bulk Operations (2 Tools)</b></summary>
<ul>
  <li>
    <strong>download_multiple</strong> – Batch download data for multiple tickers
  </li>
  <li>
    <strong>compare_stocks</strong> – Compare key metrics across stocks
  </li>
</ul>
</details>

## Installation

### Prerequisites
- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Install with uv

```bash
# Clone the repository
git clone <repository-url>
cd yahoo-finance-mcp

# Install dependencies
uv sync
```

## Usage

### With Claude Desktop

Add this configuration to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/yahoo-finance-mcp",
        "run",
        "yahoo-finance-mcp"
      ]
    }
  }
}
```

### With Claude Code

```bash
claude mcp add yahoo-finance --scope local -- uv --directory /path/to/yahoo-finance-mcp run yahoo-finance-mcp
```

### Development Mode

Test the server using the MCP inspector:

```bash
# Run in development mode
uv run mcp dev src/yahoo_finance_mcp/server.py
```

This opens a web interface where you can test all the tools interactively.

### As a Standalone Server

```bash
# Run the server
uv run yahoo-finance-mcp --http --port 8080
```

## Tool Examples

### Get Stock Information

```python
# Get comprehensive stock info
get_stock_info(ticker="AAPL")

# Get current price
get_current_price(ticker="MSFT")

# Get valuation metrics
get_market_cap(ticker="GOOGL")
```

### Historical Data

```python
# Get 1 year of daily data
get_historical_data(ticker="TSLA", period="1y", interval="1d")

# Get 5 days of hourly data
get_historical_data(ticker="NVDA", period="5d", interval="1h")

# Get dividend history
get_dividends(ticker="JNJ")
```

### Financial Statements

```python
# Get quarterly income statement
get_income_statement(ticker="AAPL", frequency="quarterly")

# Get annual balance sheet
get_balance_sheet(ticker="MSFT", frequency="annual")

# Get all financials at once
get_financials(ticker="GOOGL", frequency="quarterly")
```

### Market Analysis

```python
# Get analyst recommendations
get_analyst_recommendations(ticker="TSLA")

# Get price targets
get_analyst_price_targets(ticker="NVDA")

# Get earnings data
get_earnings(ticker="AAPL")
```

### Options Data

```python
# Get available expiration dates
get_options_dates(ticker="AAPL")

# Get full options chain for nearest expiration
get_options_chain(ticker="AAPL")

# Get options for specific date
get_options_chain(ticker="AAPL", expiration_date="2024-12-20")

# Get only calls
get_calls(ticker="AAPL", expiration_date="2024-12-20")
```

### News & Insights

```python
# Get latest 10 news articles
get_news(ticker="TSLA", limit=10)

# Get analyst upgrades/downgrades
get_upgrades_downgrades(ticker="NVDA")
```

### Market Calendars

```python
# Market-wide upcoming earnings (next 7 days, most-active only by default)
get_market_earnings_calendar(days=7)

# Restrict to $10B+ market cap, no most-active filter, up to 100 rows
get_market_earnings_calendar(
    days=14,
    market_cap=10_000_000_000,
    filter_most_active=False,
    limit=100,
)

# Other three streams take only `days`
get_market_ipo_calendar(days=30)
get_market_splits_calendar(days=30)
get_market_economic_calendar(days=7)
```

### Insider Activity

```python
# Raw per-trade log
get_insider_transactions(ticker="AAPL")

# Yahoo's aggregate 6-month buy/sell summary (not a trade list)
get_insider_purchases(ticker="AAPL")

# Current snapshot of who holds insider shares
get_insider_roster_holders(ticker="AAPL")

# Rank trades by proportional impact on each insider's own stake.
# Default 180-day window, top 10. Full exits land in a separate bucket.
get_outsized_insider_transactions(
    ticker="AAPL",
    lookback_days=180,
    top_n=10,
    sort="proportional",  # or "value" for raw $ ranking
)
```

### Bulk Operations

```python
# Compare multiple stocks
compare_stocks(tickers=["AAPL", "MSFT", "GOOGL"])

# Download historical data for multiple stocks
download_multiple(
    tickers=["AAPL", "MSFT", "GOOGL"],
    period="1mo",
    interval="1d"
)
```

## Project Structure

```
yahoo-finance-mcp/
├── src/
│   └── yahoo_finance_mcp/
│       ├── __init__.py           # Package initialization
│       ├── server.py             # Main MCP server with tool registration
│       ├── models.py             # Pydantic models for validation
│       ├── utils.py              # Helper functions and utilities
│       └── tools/
│           ├── __init__.py
│           ├── stock_info.py    # Stock information tools
│           ├── historical.py    # Historical data tools
│           ├── financials.py    # Financial statement tools
│           ├── analysis.py      # Market analysis tools
│           ├── options.py       # Options data tools
│           ├── news.py          # News and insights tools
│           └── bulk.py          # Bulk operations tools
├── tests/
│   └── test_tools.py
├── pyproject.toml
├── README.md
└── .gitignore
```

## Technical Details

### Data Source

This server uses the [yfinance](https://github.com/ranaroussi/yfinance) library to fetch data from Yahoo Finance. Please note:
- This is an unofficial API and is intended for research and educational purposes
- Data availability and accuracy depend on Yahoo Finance
- Some data may not be available for all tickers
- Rate limiting may apply for excessive requests

### Error Handling

All tools include comprehensive error handling and will return structured error responses when:
- Invalid ticker symbols are provided
- Data is not available for the requested ticker
- Network issues occur
- Invalid parameters are passed

Error responses follow this format:
```json
{
  "error": true,
  "message": "Description of the error",
  "ticker": "SYMBOL"
}
```

### Data Formatting

- All dates are returned in ISO 8601 format (YYYY-MM-DD or full datetime)
- Pandas DataFrames are converted to lists of dictionaries for easy consumption
- NaN/None values are handled gracefully
- Large datasets are formatted efficiently

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=yahoo_finance_mcp
```

### Adding New Tools

1. Create a new function in the appropriate tool module (or create a new module)
2. Import the function in `server.py`
3. Register it with the `@mcp.tool()` decorator
4. Add documentation to this README

### Code Style

The project follows standard Python conventions:
- Type hints for all function parameters and returns
- Comprehensive docstrings
- Error handling for all external API calls
- Modular organization by functionality

## Limitations

- **Not for Production Trading**: This server is for informational and research purposes only
- **Data Accuracy**: Relies on Yahoo Finance data accuracy and availability
- **Rate Limiting**: Heavy usage may encounter rate limits
- **No Real-time Guarantees**: Data may have delays depending on source
- **Terms of Service**: Users must comply with Yahoo Finance's Terms of Service

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp) - The fast, Pythonic way to build MCP servers
- Data provided by [yfinance](https://github.com/ranaroussi/yfinance)
- Part of the [Model Context Protocol](https://modelcontextprotocol.io/) ecosystem

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Disclaimer**: This project is not affiliated with, endorsed by, or connected to Yahoo Finance or Yahoo Inc. Use at your own risk and ensure compliance with Yahoo Finance's Terms of Service.
