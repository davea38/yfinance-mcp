"""Unit tests for ``tools.calendars``.

Why these tests exist
---------------------

The four market-calendar tools are the public, market-wide counterpart to the
per-ticker ``get_calendar`` in ``analysis.py``. Their *envelope shape* and
*tool naming* are load-bearing — both encode decisions from the ADR at
``docs/adr/0002-market-vs-company-calendar.md``:

* The ``event_type`` field labels each response so an LLM can tell the four
  streams apart without inspecting columns. Renaming or dropping it would
  re-introduce the polymorphism the ADR explicitly rejected.
* The ``days`` / ``start_date`` / ``end_date`` envelope echoes the requested
  window — without it an LLM can't tell whether an empty ``events`` list
  means "nothing scheduled" or "the window was 0 days".
* The window is *forward-only* from today. A regression that passes a
  historical window would silently return stale events.
* The earnings tool exposes ``market_cap`` / ``filter_most_active`` /
  ``limit`` because earnings season can overflow the LLM's context; the
  other three tools must *not* sprout those parameters by accident (the spec
  keeps them lean intentionally).
* Errors return ``{"error": True, "message": ..., "operation": ...}`` with
  no ``ticker`` key — market calendars aren't ticker-scoped.

We mock ``yfinance.Calendars`` end-to-end so tests never hit the network.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from tools import calendars


# ---------------------------------------------------------------------------
# Fake Calendars
# ---------------------------------------------------------------------------


class FakeCalendars:
    """Minimal stand-in for ``yfinance.Calendars``.

    Records the ``start`` / ``end`` it was constructed with plus the args
    passed to each method, and returns a configurable DataFrame on each
    method call. The default returned frame is empty; tests set
    ``FakeCalendars.next_frame`` (a DataFrame) or
    ``FakeCalendars.raise_error`` (an Exception) before invoking the tool.
    """

    last: "FakeCalendars | None" = None
    next_frame: pd.DataFrame | None = None
    raise_error: Exception | None = None

    def __init__(self, start=None, end=None, session=None):
        self.start = start
        self.end = end
        self.session = session
        self.calls: list[tuple[str, dict]] = []
        FakeCalendars.last = self

    def _dispatch(self, method: str, **kwargs):
        self.calls.append((method, kwargs))
        if FakeCalendars.raise_error is not None:
            raise FakeCalendars.raise_error
        if FakeCalendars.next_frame is not None:
            return FakeCalendars.next_frame
        return pd.DataFrame()

    def get_earnings_calendar(self, **kwargs):
        return self._dispatch("get_earnings_calendar", **kwargs)

    def get_ipo_info_calendar(self, **kwargs):
        return self._dispatch("get_ipo_info_calendar", **kwargs)

    def get_splits_calendar(self, **kwargs):
        return self._dispatch("get_splits_calendar", **kwargs)

    def get_economic_events_calendar(self, **kwargs):
        return self._dispatch("get_economic_events_calendar", **kwargs)


@pytest.fixture(autouse=True)
def _reset_fake_calendars(monkeypatch):
    """Reset class-level state and patch ``yf.Calendars`` for every test."""
    FakeCalendars.last = None
    FakeCalendars.next_frame = None
    FakeCalendars.raise_error = None
    monkeypatch.setattr(calendars.yf, "Calendars", FakeCalendars)
    yield
    FakeCalendars.last = None
    FakeCalendars.next_frame = None
    FakeCalendars.raise_error = None


def _make_earnings_frame():
    return pd.DataFrame(
        [
            {
                "Company": "Apple Inc.",
                "Marketcap": 3_000_000_000_000,
                "Event Start Date": pd.Timestamp("2026-05-20T16:00:00"),
            },
            {
                "Company": "Microsoft Corp.",
                "Marketcap": 2_800_000_000_000,
                "Event Start Date": pd.Timestamp("2026-05-21T16:00:00"),
            },
        ],
        index=pd.Index(["AAPL", "MSFT"], name="Symbol"),
    )


# ---------------------------------------------------------------------------
# Earnings calendar
# ---------------------------------------------------------------------------


class TestEarningsCalendar:
    def test_happy_path_envelope_shape(self):
        FakeCalendars.next_frame = _make_earnings_frame()
        out = calendars.get_market_earnings_calendar(days=7)

        assert set(out) == {
            "event_type",
            "days",
            "start_date",
            "end_date",
            "count",
            "events",
        }
        assert out["event_type"] == "earnings"
        assert out["days"] == 7
        assert out["count"] == 2
        assert len(out["events"]) == 2
        # Envelope reports forward-only window from today
        today = date.today()
        assert out["start_date"] == today.isoformat()
        assert out["end_date"] == (today + timedelta(days=7)).isoformat()

    def test_default_days_is_seven(self):
        FakeCalendars.next_frame = pd.DataFrame()
        out = calendars.get_market_earnings_calendar()
        assert out["days"] == 7

    def test_forwards_filter_args_to_yfinance(self):
        FakeCalendars.next_frame = pd.DataFrame()
        calendars.get_market_earnings_calendar(
            days=14,
            market_cap=10_000_000_000,
            filter_most_active=False,
            limit=25,
        )
        method, kwargs = FakeCalendars.last.calls[0]
        assert method == "get_earnings_calendar"
        assert kwargs == {
            "market_cap": 10_000_000_000,
            "filter_most_active": False,
            "limit": 25,
        }

    def test_calendars_constructed_with_window(self):
        FakeCalendars.next_frame = pd.DataFrame()
        calendars.get_market_earnings_calendar(days=3)
        today = date.today()
        assert FakeCalendars.last.start == today.isoformat()
        assert FakeCalendars.last.end == (today + timedelta(days=3)).isoformat()

    def test_limit_capped_at_100(self):
        FakeCalendars.next_frame = pd.DataFrame()
        calendars.get_market_earnings_calendar(limit=500)
        _, kwargs = FakeCalendars.last.calls[0]
        assert kwargs["limit"] == 100

    def test_default_filter_most_active_true(self):
        FakeCalendars.next_frame = pd.DataFrame()
        calendars.get_market_earnings_calendar()
        _, kwargs = FakeCalendars.last.calls[0]
        assert kwargs["filter_most_active"] is True
        # Default limit per spec
        assert kwargs["limit"] == 50
        # No market_cap floor by default
        assert kwargs["market_cap"] is None

    def test_empty_response_returns_empty_events(self):
        FakeCalendars.next_frame = pd.DataFrame()
        out = calendars.get_market_earnings_calendar(days=7)
        assert out["count"] == 0
        assert out["events"] == []

    def test_error_path(self):
        FakeCalendars.raise_error = RuntimeError("yahoo on fire")
        out = calendars.get_market_earnings_calendar(days=7)
        assert out["error"] is True
        assert "yahoo on fire" in out["message"]
        assert out["operation"] == "fetching market earnings calendar"
        # Market-wide errors must NOT carry a ticker field
        assert "ticker" not in out

    @pytest.mark.parametrize("bad", [0, -1, "7", 1.5, True])
    def test_days_validation(self, bad):
        out = calendars.get_market_earnings_calendar(days=bad)
        assert out["error"] is True
        assert "days" in out["message"]

    @pytest.mark.parametrize("bad", [0, -1, "10", 1.5, True])
    def test_limit_validation(self, bad):
        out = calendars.get_market_earnings_calendar(limit=bad)
        assert out["error"] is True
        assert "limit" in out["message"]

    @pytest.mark.parametrize("bad", ["billion", -1, True])
    def test_market_cap_validation(self, bad):
        out = calendars.get_market_earnings_calendar(market_cap=bad)
        assert out["error"] is True
        assert "market_cap" in out["message"]

    def test_filter_most_active_validation(self):
        out = calendars.get_market_earnings_calendar(filter_most_active="yes")
        assert out["error"] is True
        assert "filter_most_active" in out["message"]


# ---------------------------------------------------------------------------
# IPO calendar
# ---------------------------------------------------------------------------


class TestIpoCalendar:
    def test_happy_path_calls_ipo_info_method(self):
        FakeCalendars.next_frame = pd.DataFrame(
            [{"Company": "Acme", "Date": pd.Timestamp("2026-05-19")}],
            index=pd.Index(["ACME"], name="Symbol"),
        )
        out = calendars.get_market_ipo_calendar(days=14)

        assert out["event_type"] == "ipo"
        assert out["days"] == 14
        assert out["count"] == 1
        method, _ = FakeCalendars.last.calls[0]
        # Tool surface uses ipo, underlying yfinance method is
        # `get_ipo_info_calendar` — this guards against accidentally calling
        # a non-existent `get_ipo_calendar`.
        assert method == "get_ipo_info_calendar"

    def test_envelope_no_extra_params(self):
        # IPO tool intentionally takes only `days` per the ADR — guard
        # against accidental parameter creep.
        FakeCalendars.next_frame = pd.DataFrame()
        import inspect

        sig = inspect.signature(calendars.get_market_ipo_calendar)
        assert list(sig.parameters) == ["days"]

    def test_calendars_constructed_with_window(self):
        """Forward-only window is load-bearing per the ADR — a regression that
        passed a historical window would silently return stale events."""
        FakeCalendars.next_frame = pd.DataFrame()
        calendars.get_market_ipo_calendar(days=21)
        today = date.today()
        assert FakeCalendars.last.start == today.isoformat()
        assert FakeCalendars.last.end == (today + timedelta(days=21)).isoformat()

    def test_error_path(self):
        FakeCalendars.raise_error = RuntimeError("boom")
        out = calendars.get_market_ipo_calendar()
        assert out["error"] is True
        assert out["operation"] == "fetching market IPO calendar"

    @pytest.mark.parametrize("bad", [0, -1, "7", 1.5, True])
    def test_days_validation(self, bad):
        out = calendars.get_market_ipo_calendar(days=bad)
        assert out["error"] is True
        assert "days" in out["message"]


# ---------------------------------------------------------------------------
# Splits calendar
# ---------------------------------------------------------------------------


class TestSplitsCalendar:
    def test_happy_path(self):
        FakeCalendars.next_frame = pd.DataFrame(
            [{"Company": "Acme", "Payable On": pd.Timestamp("2026-05-19")}],
            index=pd.Index(["ACME"], name="Symbol"),
        )
        out = calendars.get_market_splits_calendar(days=30)
        assert out["event_type"] == "splits"
        assert out["days"] == 30
        assert out["count"] == 1
        method, _ = FakeCalendars.last.calls[0]
        assert method == "get_splits_calendar"

    def test_signature_only_days(self):
        import inspect

        sig = inspect.signature(calendars.get_market_splits_calendar)
        assert list(sig.parameters) == ["days"]

    def test_calendars_constructed_with_window(self):
        FakeCalendars.next_frame = pd.DataFrame()
        calendars.get_market_splits_calendar(days=10)
        today = date.today()
        assert FakeCalendars.last.start == today.isoformat()
        assert FakeCalendars.last.end == (today + timedelta(days=10)).isoformat()

    def test_error_path(self):
        FakeCalendars.raise_error = RuntimeError("boom")
        out = calendars.get_market_splits_calendar()
        assert out["error"] is True
        assert out["operation"] == "fetching market splits calendar"

    @pytest.mark.parametrize("bad", [0, -1, "7", 1.5, True])
    def test_days_validation(self, bad):
        out = calendars.get_market_splits_calendar(days=bad)
        assert out["error"] is True
        assert "days" in out["message"]


# ---------------------------------------------------------------------------
# Economic calendar
# ---------------------------------------------------------------------------


class TestEconomicCalendar:
    def test_happy_path_calls_economic_events_method(self):
        FakeCalendars.next_frame = pd.DataFrame(
            [{"Region": "US", "Event Time": pd.Timestamp("2026-05-19T08:30")}],
            index=pd.Index(["CPI"], name="Event"),
        )
        out = calendars.get_market_economic_calendar(days=7)
        assert out["event_type"] == "economic"
        method, _ = FakeCalendars.last.calls[0]
        # Underlying yfinance method is `get_economic_events_calendar`.
        assert method == "get_economic_events_calendar"

    def test_signature_only_days(self):
        import inspect

        sig = inspect.signature(calendars.get_market_economic_calendar)
        assert list(sig.parameters) == ["days"]

    def test_error_path(self):
        FakeCalendars.raise_error = RuntimeError("boom")
        out = calendars.get_market_economic_calendar()
        assert out["error"] is True
        assert out["operation"] == "fetching market economic calendar"

    def test_calendars_constructed_with_window(self):
        FakeCalendars.next_frame = pd.DataFrame()
        calendars.get_market_economic_calendar(days=5)
        today = date.today()
        assert FakeCalendars.last.start == today.isoformat()
        assert FakeCalendars.last.end == (today + timedelta(days=5)).isoformat()

    @pytest.mark.parametrize("bad", [0, -1, "7", 1.5, True])
    def test_days_validation(self, bad):
        out = calendars.get_market_economic_calendar(days=bad)
        assert out["error"] is True
        assert "days" in out["message"]


# ---------------------------------------------------------------------------
# Server registration smoke test
# ---------------------------------------------------------------------------


def test_server_registers_all_four_market_tools():
    """server.py must wrap each tool with the spec-prescribed name.

    The `market_` prefix is load-bearing per the ADR; renaming a wrapper
    silently to drop it would re-introduce the disambiguation problem the
    ADR fixed."""
    import server

    for name in (
        "get_market_earnings_calendar",
        "get_market_ipo_calendar",
        "get_market_splits_calendar",
        "get_market_economic_calendar",
    ):
        assert hasattr(server, name), f"server.py is missing {name} wrapper"
