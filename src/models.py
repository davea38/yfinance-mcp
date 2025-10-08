"""Pydantic models for Yahoo Finance MCP server."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class StockInfoResponse(BaseModel):
    """Response model for stock information."""
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    average_volume: Optional[int] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None


class HistoricalDataRequest(BaseModel):
    """Request model for historical data."""
    ticker: str = Field(..., description="Stock ticker symbol")
    period: str = Field(default="1mo", description="Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)")
    interval: str = Field(default="1d", description="Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)")

    @field_validator('period')
    @classmethod
    def validate_period(cls, v):
        valid_periods = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max']
        if v not in valid_periods:
            raise ValueError(f"Invalid period. Must be one of: {', '.join(valid_periods)}")
        return v

    @field_validator('interval')
    @classmethod
    def validate_interval(cls, v):
        valid_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']
        if v not in valid_intervals:
            raise ValueError(f"Invalid interval. Must be one of: {', '.join(valid_intervals)}")
        return v


class FinancialStatementRequest(BaseModel):
    """Request model for financial statements."""
    ticker: str = Field(..., description="Stock ticker symbol")
    frequency: str = Field(default="quarterly", description="Statement frequency (quarterly or annual)")

    @field_validator('frequency')
    @classmethod
    def validate_frequency(cls, v):
        if v not in ['quarterly', 'annual']:
            raise ValueError("Frequency must be 'quarterly' or 'annual'")
        return v


class OptionsRequest(BaseModel):
    """Request model for options data."""
    ticker: str = Field(..., description="Stock ticker symbol")
    expiration_date: Optional[str] = Field(None, description="Option expiration date (YYYY-MM-DD format)")


class NewsItem(BaseModel):
    """Model for a news article."""
    title: str
    publisher: Optional[str] = None
    link: Optional[str] = None
    published: Optional[datetime] = None
    type: Optional[str] = None
    thumbnail: Optional[Dict[str, Any]] = None


class AnalystRecommendation(BaseModel):
    """Model for analyst recommendation."""
    date: Optional[str] = None
    firm: Optional[str] = None
    to_grade: Optional[str] = None
    from_grade: Optional[str] = None
    action: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: bool = True
    message: str
    ticker: Optional[str] = None
    operation: Optional[str] = None
