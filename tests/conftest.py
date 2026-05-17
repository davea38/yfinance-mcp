"""Shared pytest fixtures for the Yahoo Finance MCP test suite.

Tests must not hit the live Yahoo endpoint — yfinance is rate-limited and the
data changes daily. We patch ``yfinance.Ticker`` (and the symbol re-exported
into the tool modules under test) so each test controls exactly what comes
back.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest


# The package layout is ``src/`` flat (no top-level package); the build script
# runs `uv run pytest` from the project root, so we have to put `src/` on
# ``sys.path`` ourselves before the test modules import.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class StubTicker:
    """Minimal stand-in for ``yfinance.Ticker`` used in unit tests.

    Each attribute is settable per-test via the ``attrs`` dict; missing
    attributes raise ``AttributeError`` so we never accidentally fall through
    to a real network call.
    """

    def __init__(self, symbol: str, attrs: Dict[str, Any]):
        self.symbol = symbol
        self._attrs = attrs

    def __getattr__(self, name: str) -> Any:
        attrs = self.__dict__.get("_attrs", {})
        if name in attrs:
            return attrs[name]
        raise AttributeError(name)


@pytest.fixture
def stub_ticker_factory(monkeypatch):
    """Return a callable ``(module, attrs) -> StubTicker``.

    The factory patches the ``yf.Ticker`` symbol *inside the tool module under
    test* (each tool module does ``import yfinance as yf``), so the patch is
    isolated to that module and unrelated tests don't see leaks.
    """

    def _factory(module, attrs: Dict[str, Any]):
        stub = {"last": None}

        def _ticker_ctor(symbol: str) -> StubTicker:
            t = StubTicker(symbol, attrs)
            stub["last"] = t
            return t

        monkeypatch.setattr(module.yf, "Ticker", _ticker_ctor)
        return stub

    return _factory
