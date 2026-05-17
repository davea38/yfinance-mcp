"""Unit tests for FastMCP server registration in ``server.py``.

Why these tests exist
---------------------

``server.py`` is the public surface of the MCP server — it is the file that
MCP clients discover tools from. Any drift between:

* the spec-prescribed tool names,
* the registered wrappers in ``server.py``, and
* the README's advertised tool count

breaks LLM tool lookup silently, because the client just won't find the tool.
These tests enforce the three-way contract at CI time so a rename or accidental
omission is caught before it ships.

Specifically:

* The expected count (36) is the source of truth for the build loop — the
  test fails loudly when a tool is added or removed without updating the count.
* Every spec-prescribed name is asserted individually so the failure message
  tells you *which* tool is missing.
* Every registered tool must have a non-empty description (docstring); an
  empty description renders the tool invisible to LLMs.
* The README must agree with the actual registration count; divergence means
  the documentation is misleading users.

Tests do not hit the network — they only inspect the server module's
registration metadata.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_TOOL_COUNT = 36

# All tool names prescribed by the spec, organised by category for readability.
EXPECTED_TOOL_NAMES: list[str] = [
    # stock_info
    "get_stock_info",
    "get_current_price",
    "get_market_cap",
    "get_major_holders",
    "get_institutional_holders",
    "get_mutualfund_holders",
    # historical
    "get_historical_data",
    "get_dividends",
    "get_splits",
    "get_actions",
    "get_capital_gains",
    # financials
    "get_income_statement",
    "get_balance_sheet",
    "get_cash_flow",
    "get_financials",
    # analysis
    "get_analyst_recommendations",
    "get_analyst_price_targets",
    "get_earnings",
    "get_earnings_dates",
    "get_calendar",
    # options
    "get_options_dates",
    "get_options_chain",
    "get_calls",
    "get_puts",
    # news
    "get_news",
    "get_upgrades_downgrades",
    # insiders
    "get_insider_transactions",
    "get_insider_purchases",
    "get_insider_roster_holders",
    "get_outsized_insider_transactions",
    # calendars
    "get_market_earnings_calendar",
    "get_market_ipo_calendar",
    "get_market_splits_calendar",
    "get_market_economic_calendar",
    # bulk
    "download_multiple",
    "compare_stocks",
]

_README_PATH = Path(__file__).resolve().parent.parent / "README.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_registered_tools():
    """Return the list of Tool objects registered on the FastMCP instance.

    Uses ``asyncio.run(mcp.list_tools())`` which is the stable public API and
    returns Tool objects with ``.name`` and ``.description`` attributes.
    """
    import server  # noqa: PLC0415 — import inside function keeps module-level clean

    return asyncio.run(server.mcp.list_tools())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolCount:
    """The registered count must exactly match the spec total."""

    def test_registered_count_matches_expected(self):
        """Exactly EXPECTED_TOOL_COUNT tools must be registered.

        Fail loudly if a tool is added or removed without updating the
        constant — this drives the build loop to keep everything in sync.
        """
        tools = _get_registered_tools()
        registered_names = [t.name for t in tools]
        assert len(tools) == EXPECTED_TOOL_COUNT, (
            f"Expected {EXPECTED_TOOL_COUNT} registered tools, "
            f"got {len(tools)}.\n"
            f"Registered: {sorted(registered_names)}"
        )


class TestToolNames:
    """Every spec-prescribed name must appear in the registered tool list."""

    def test_all_expected_names_are_registered(self):
        """No tool name from the spec may be absent from the registration.

        Checks the full set in one assertion so a single failure lists every
        missing name, not just the first.
        """
        tools = _get_registered_tools()
        registered_names = {t.name for t in tools}
        missing = [name for name in EXPECTED_TOOL_NAMES if name not in registered_names]
        assert not missing, (
            f"The following tools are in the spec but not registered in server.py:\n"
            + "\n".join(f"  - {name}" for name in missing)
        )

    @pytest.mark.parametrize("name", EXPECTED_TOOL_NAMES)
    def test_individual_tool_registered(self, name: str):
        """Each expected tool name is registered — individual parametrised
        assertion so CI output pinpoints exactly which name is missing."""
        tools = _get_registered_tools()
        registered_names = {t.name for t in tools}
        assert name in registered_names, (
            f"Tool '{name}' is missing from the FastMCP registration in server.py"
        )


class TestToolDescriptions:
    """Every registered tool must carry a non-empty description."""

    def test_all_tools_have_non_empty_description(self):
        """A blank or missing description makes the tool invisible to LLMs.

        Checks all tools in one shot; the failure message names every offender.
        """
        tools = _get_registered_tools()
        empty = [
            t.name
            for t in tools
            if not (t.description and t.description.strip())
        ]
        assert not empty, (
            "The following tools have empty or missing descriptions:\n"
            + "\n".join(f"  - {name}" for name in empty)
        )

    @pytest.mark.parametrize("name", EXPECTED_TOOL_NAMES)
    def test_individual_tool_has_description(self, name: str):
        """Each expected tool individually has a non-empty description."""
        tools = _get_registered_tools()
        tool_map = {t.name: t for t in tools}
        if name not in tool_map:
            pytest.skip(f"Tool '{name}' not registered — covered by TestToolNames")
        tool = tool_map[name]
        assert tool.description and tool.description.strip(), (
            f"Tool '{name}' has an empty or missing description (docstring)"
        )


class TestReadmeSync:
    """The README must advertise the same tool count as the server registers.

    If README and server diverge, users are misled about what the server
    provides. This test drives the build loop to keep documentation honest.
    """

    def test_readme_tool_count_matches_registration(self):
        """README must reference the string '36' as the tool count.

        The pattern ``**36 tools**`` (or any digit sequence matching the
        actual registration count) is searched in the README. If the README
        references a different number, or no number at all, the test fails
        with a message pointing to the line that needs updating.
        """
        assert _README_PATH.exists(), (
            f"README not found at {_README_PATH} — cannot verify tool count claim"
        )

        tools = _get_registered_tools()
        actual_count = len(tools)

        readme_text = _README_PATH.read_text(encoding="utf-8")

        # Look for any occurrence of the actual count next to "tool(s)"
        # e.g. "36 tools", "**36 tools**", "36-tool", etc.
        pattern = rf"\b{actual_count}\b"
        count_occurrences = re.findall(pattern, readme_text)

        # Also specifically check for the canonical phrase the README uses.
        canonical_phrase = f"{actual_count} tools"
        has_canonical = canonical_phrase in readme_text

        assert has_canonical, (
            f"README does not contain the phrase '{canonical_phrase}'.\n"
            f"The server has {actual_count} registered tools but the README "
            f"appears to advertise a different count.\n"
            f"Found occurrences of '{actual_count}' in README: {len(count_occurrences)}.\n"
            f"Update README.md to say '{canonical_phrase}' to keep docs in sync."
        )

    def test_readme_expected_count_constant_matches_registration(self):
        """EXPECTED_TOOL_COUNT constant in this test file must match the
        actual registration. If the server gains a tool and the constant is
        not updated, this test catches the desync before the count test does.
        """
        tools = _get_registered_tools()
        actual_count = len(tools)
        assert EXPECTED_TOOL_COUNT == actual_count, (
            f"EXPECTED_TOOL_COUNT={EXPECTED_TOOL_COUNT} is out of date. "
            f"The server currently registers {actual_count} tools. "
            f"Update the constant in this file."
        )
