# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Yahoo Finance MCP Server - A Model Context Protocol server providing 30 tools for accessing Yahoo Finance data. Built with FastMCP and yfinance.

## Package Manager

**Always use `uv`** for all Python operations:
- `uv sync` - Install/sync dependencies
- `uv run <command>` - Run Python scripts or commands
- `uv run pytest` - Run tests

## Development Commands

### Testing the Server
```bash
# Interactive development mode with web UI
uv run mcp dev src/server.py

# Run as standalone server (stdio mode)
uv run yahoo-finance-mcp
```

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=server --cov=utils --cov=tools

# Run specific test file
uv run pytest tests/test_insiders.py
```

### Code Validation
```bash
# Import validation
uv run python -c "import server; print('✓ Imports successful')"
```

## Architecture

### Tool Registration Pattern

All MCP tools follow this pattern in `server.py`:

1. **Import tool modules** (not individual functions):
   ```python
   from .tools import stock_info, historical, financials, analysis, options, news, bulk
   ```

2. **Register with @mcp.tool() decorator** as wrapper functions:
   ```python
   @mcp.tool()
   def get_stock_info(ticker: str) -> Dict[str, Any]:
       """Docstring visible to LLM."""
       return stock_info.get_stock_info(ticker)
   ```

This pattern keeps tool logic in modules while making them discoverable to MCP clients.

### Tool Module Structure

Each tool module (`tools/*.py`) contains:
- Pure Python functions (no decorators in modules)
- Comprehensive error handling using `handle_yfinance_error()`
- Input validation using `validate_*()` functions from utils
- Data formatting using `format_dataframe_to_dict()` or `format_series_to_dict()`

### Data Flow

```
MCP Client → server.py (@mcp.tool wrapper) → tools/*.py (implementation)
→ yfinance API → utils.py (formatting) → structured dict response
```

### Error Response Format

All tools return consistent error structure:
```python
{
    "error": True,
    "message": "Description of error",
    "ticker": "SYMBOL"  # optional
}
```

## Adding New Tools

1. **Create function in appropriate tool module** (e.g., `tools/stock_info.py`):
   ```python
   def get_new_data(ticker: str, param: str = "default") -> Dict[str, Any]:
       """Detailed docstring for implementation."""
       try:
           ticker = validate_ticker_symbol(ticker)
           stock = yf.Ticker(ticker)
           data = stock.some_property
           return {"ticker": ticker, "data": format_dataframe_to_dict(data)}
       except Exception as e:
           return handle_yfinance_error(e, ticker, "fetching new data")
   ```

2. **Register in server.py**:
   ```python
   @mcp.tool()
   def get_new_data(ticker: str, param: str = "default") -> Dict[str, Any]:
       """Brief description for LLM - focuses on what, not how."""
       return stock_info.get_new_data(ticker, param)
   ```

3. **Key requirements**:
   - Type hints on all parameters and returns
   - Error handling with try/except
   - Input validation for ticker symbols
   - Consistent return structure (dict with ticker + data/error)

## Tool Categories (30 tools total)

- **stock_info.py** (6): Basic company info, prices, holders
- **historical.py** (5): Price history, dividends, splits
- **financials.py** (4): Income statement, balance sheet, cash flow
- **analysis.py** (5): Analyst recommendations, earnings, price targets
- **options.py** (4): Options chains, calls, puts, expiration dates
- **news.py** (2): News articles, upgrades/downgrades
- **bulk.py** (2): Multi-ticker operations, comparisons

## Key Utilities (utils.py)

- `format_dataframe_to_dict()` - Converts pandas DataFrames to JSON-serializable dicts
- `format_series_to_dict()` - Converts pandas Series to dicts
- `validate_ticker_symbol()` - Normalizes and validates ticker symbols
- `validate_period()` / `validate_interval()` - Validates historical data parameters
- `handle_yfinance_error()` - Creates consistent error responses
- `format_financial_statement()` - Specialized formatting for financial statements

All utilities handle pandas timestamps, NaN values, and numpy types properly.

## Configuration for Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/rush/projects/2025/stockview/yahoo-finance-mcp",
        "run",
        "yahoo-finance-mcp"
      ]
    }
  }
}
```

## Important Constraints

- **Python 3.10+** required
- **yfinance unofficial API** - for research/educational purposes only
- Data availability varies by ticker and Yahoo Finance
- All dates returned in ISO 8601 format
- No authentication/API keys needed
- Rate limiting may occur with heavy usage
