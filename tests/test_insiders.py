"""Unit tests for ``tools.insiders``.

Why these tests exist
---------------------

The four insider tools answer four different questions and the analytical one
(`get_outsized_insider_transactions`) makes load-bearing structural decisions
that are easy to break with an innocent refactor:

* The bucket split between ``outsized_transactions`` and ``full_liquidations``
  is the whole point of the ADR — a regression that silently merges them, or
  drops the liquidations bucket, defeats the tool's purpose.
* The ranking is by ``abs(shares_transacted / insider_current_holdings)`` —
  swapping to ``value``-based or losing the ``abs`` would break the "loud signal
  surfaces first" contract.
* ``lookback_days`` is part of the contract; tightening it later is a breaking
  change for callers.
* ``transaction_type`` is surfaced verbatim — pre-filtering ``Stock Award`` /
  ``Option Exercise`` would hide that the underlying ratio is mechanically
  inflated.

The pass-through tools are also covered because their *shape* (ticker key +
named bucket) is what downstream LLM prompts depend on; an accidental rename
from ``insider_transactions`` to ``transactions`` would silently confuse
clients.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tools import insiders


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_txns(rows):
    """Build an insider_transactions DataFrame matching yfinance's column order."""
    return pd.DataFrame(
        rows,
        columns=[
            "Shares",
            "Value",
            "URL",
            "Text",
            "Insider",
            "Position",
            "Transaction",
            "Start Date",
            "Ownership",
        ],
    )


def _make_roster(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "Name",
            "Position",
            "URL",
            "Most Recent Transaction",
            "Latest Transaction Date",
            "Shares Owned Directly",
            "Position Direct Date",
        ],
    )


@pytest.fixture
def sample_txns():
    """Mixed bag of trades: equal-proportional buy/sell, a stock award, and a
    full-liquidation row whose actor is missing from the roster."""
    # 'today' anchored well within any reasonable lookback_days default.
    today = pd.Timestamp("2026-05-10")
    return _make_txns(
        [
            # 90% sale by a current holder — should top the proportional ranking.
            [9_000, 900_000.0, "", "Sale at 100", "ALICE A", "CEO", "Sale", today, "D"],
            # 90% purchase by a different current holder — ties on abs ratio.
            [4_500, 450_000.0, "", "Purchase at 100", "BOB B", "CFO", "Purchase", today, "D"],
            # 10% trim — smaller proportional move but largest dollar value.
            [10_000, 5_000_000.0, "", "Sale at 500", "CAROL C", "Director", "Sale", today, "D"],
            # Stock award — mechanically large ratio but not a market signal.
            [500, 0.0, "", "Stock Award", "ALICE A", "CEO", "Stock Award", today, "D"],
            # Full liquidation: insider not on the roster.
            [2_000, 200_000.0, "", "Sale at 100", "DAVE D", "Officer", "Sale", today, "D"],
            # Way outside the default lookback window — must be filtered out.
            [1_000_000, 99_999_999.0, "", "Old trade", "ALICE A", "CEO", "Sale", pd.Timestamp("2000-01-01"), "D"],
        ]
    )


@pytest.fixture
def sample_roster():
    return _make_roster(
        [
            ["ALICE A", "CEO", "", "Sale", pd.Timestamp("2026-05-10"), 10_000.0, pd.Timestamp("2026-05-10")],
            ["BOB B", "CFO", "", "Purchase", pd.Timestamp("2026-05-10"), 5_000.0, pd.Timestamp("2026-05-10")],
            ["CAROL C", "Director", "", "Sale", pd.Timestamp("2026-05-10"), 100_000.0, pd.Timestamp("2026-05-10")],
            # DAVE D intentionally absent — drives the full_liquidations bucket.
        ]
    )


# ---------------------------------------------------------------------------
# Pass-through tools — shape + error path
# ---------------------------------------------------------------------------


def test_get_insider_transactions_passthrough_shape(stub_ticker_factory, sample_txns):
    """Happy path: dict with ticker + named bucket; rows preserved."""
    stub_ticker_factory(insiders, {"insider_transactions": sample_txns})

    result = insiders.get_insider_transactions("aapl")

    assert result["ticker"] == "AAPL"  # validate_ticker_symbol normalizes
    assert "insider_transactions" in result
    # One row per input txn.
    assert len(result["insider_transactions"]) == len(sample_txns)
    # Required columns survive formatting.
    first = result["insider_transactions"][0]
    for required in ("Shares", "Value", "Insider", "Position", "Transaction", "Start Date"):
        assert required in first


def test_get_insider_transactions_empty_returns_error(stub_ticker_factory):
    stub_ticker_factory(insiders, {"insider_transactions": pd.DataFrame()})
    result = insiders.get_insider_transactions("AAPL")
    assert result["error"] is True
    assert result["ticker"] == "AAPL"


def test_get_insider_purchases_passthrough_shape(stub_ticker_factory):
    df = pd.DataFrame(
        {
            "Insider Purchases Last 6m": ["Purchases", "Sales", "Net"],
            "Shares": [100.0, 50.0, 50.0],
            "Trans": [3, 2, 5],
        }
    )
    stub_ticker_factory(insiders, {"insider_purchases": df})
    result = insiders.get_insider_purchases("AAPL")
    assert result["ticker"] == "AAPL"
    assert len(result["insider_purchases"]) == 3


def test_get_insider_purchases_empty_returns_error(stub_ticker_factory):
    stub_ticker_factory(insiders, {"insider_purchases": None})
    result = insiders.get_insider_purchases("AAPL")
    assert result["error"] is True


def test_get_insider_roster_holders_passthrough_shape(stub_ticker_factory, sample_roster):
    stub_ticker_factory(insiders, {"insider_roster_holders": sample_roster})
    result = insiders.get_insider_roster_holders("AAPL")
    assert result["ticker"] == "AAPL"
    assert len(result["insider_roster_holders"]) == len(sample_roster)


def test_get_insider_roster_holders_empty_returns_error(stub_ticker_factory):
    stub_ticker_factory(insiders, {"insider_roster_holders": pd.DataFrame()})
    result = insiders.get_insider_roster_holders("AAPL")
    assert result["error"] is True


# ---------------------------------------------------------------------------
# Analytical tool — the load-bearing logic
# ---------------------------------------------------------------------------


def test_outsized_no_roster_returns_clean_error(stub_ticker_factory, sample_txns):
    """Spec: empty roster -> directional error pointing at get_insider_transactions."""
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": pd.DataFrame(),
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL")
    assert result["error"] is True
    assert "get_insider_transactions" in result["message"]


def test_outsized_splits_liquidations_from_ranked(
    stub_ticker_factory, sample_txns, sample_roster
):
    """DAVE D is absent from roster -> his trade lands in full_liquidations,
    never in outsized_transactions."""
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions(
        "AAPL", lookback_days=10_000  # wide window so the 2000-01-01 row would *also* qualify date-wise
    )

    outsized_names = {row["name"] for row in result["outsized_transactions"]}
    liquidation_names = {row["name"] for row in result["full_liquidations"]}

    assert "DAVE D" in liquidation_names
    assert "DAVE D" not in outsized_names
    # Full liquidations carry insider_current_holdings==0 per spec response shape.
    for row in result["full_liquidations"]:
        assert row["insider_current_holdings"] == 0
        assert row["holdings_pct_change"] is None


def test_outsized_ranking_is_by_abs_proportional(
    stub_ticker_factory, sample_txns, sample_roster
):
    """ALICE 90% sale and BOB 90% purchase tie at the top; CAROL 10% trim ranks
    below despite carrying the largest raw dollar value."""
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL", top_n=10)
    rows = result["outsized_transactions"]
    # Top two rows must be ALICE's sale (0.9) and BOB's purchase (0.9) — equal abs ratio.
    top_two = {(rows[0]["name"], rows[0]["transaction_type"]),
               (rows[1]["name"], rows[1]["transaction_type"])}
    assert top_two == {("ALICE A", "Sale"), ("BOB B", "Purchase")}
    # CAROL's 10% trim must rank strictly below — even though her trade has the
    # largest raw dollar value in the sample.
    carol_idx = next(i for i, r in enumerate(rows) if r["name"] == "CAROL C")
    assert carol_idx >= 2


def test_outsized_value_sort_is_secondary(
    stub_ticker_factory, sample_txns, sample_roster
):
    """sort='value' inverts the ordering — CAROL's $5M sale tops the list."""
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL", sort="value", top_n=10)
    assert result["outsized_transactions"][0]["name"] == "CAROL C"


def test_outsized_lookback_window_filters_old_rows(
    stub_ticker_factory, sample_txns, sample_roster
):
    """A row dated 2000-01-01 must NOT appear under the default 180-day window."""
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL", lookback_days=180, top_n=50)
    rows = result["outsized_transactions"] + result["full_liquidations"]
    # The 2000-01-01 ALICE row carried 1_000_000 shares — would dominate if not filtered.
    assert all((row.get("shares_transacted") or 0) < 1_000_000 for row in rows)


def test_outsized_transaction_type_surfaced_verbatim(
    stub_ticker_factory, sample_txns, sample_roster
):
    """Stock Award rows must appear with transaction_type=='Stock Award', not
    pre-filtered. Mechanical ratio inflation is the LLM's problem, not ours."""
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL", top_n=50)
    types = {row["transaction_type"] for row in result["outsized_transactions"]}
    assert "Stock Award" in types


def test_outsized_top_n_caps_only_outsized_not_liquidations(
    stub_ticker_factory, sample_roster
):
    """top_n caps the ranked list. full_liquidations stays uncapped within the
    window — full exits are the loudest signal and must never be hidden."""
    today = pd.Timestamp("2026-05-10")
    # Five separate liquidation rows from people who aren't on the roster.
    liq_rows = _make_txns(
        [
            [1000 * (i + 1), 1000.0 * (i + 1), "", "", f"GHOST {i}", "Officer", "Sale", today, "D"]
            for i in range(5)
        ]
    )
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": liq_rows,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL", top_n=1)
    assert len(result["outsized_transactions"]) == 0
    assert len(result["full_liquidations"]) == 5


def test_outsized_returns_lookback_days_in_response(
    stub_ticker_factory, sample_txns, sample_roster
):
    """The response carries lookback_days so the LLM knows the window it got."""
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL", lookback_days=42)
    assert result["lookback_days"] == 42


def test_outsized_rejects_bad_sort(stub_ticker_factory, sample_txns, sample_roster):
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    result = insiders.get_outsized_insider_transactions("AAPL", sort="dollars")
    assert result["error"] is True


def test_outsized_rejects_non_positive_lookback(
    stub_ticker_factory, sample_txns, sample_roster
):
    stub_ticker_factory(
        insiders,
        {
            "insider_transactions": sample_txns,
            "insider_roster_holders": sample_roster,
        },
    )
    assert insiders.get_outsized_insider_transactions("AAPL", lookback_days=0)["error"]
    assert insiders.get_outsized_insider_transactions("AAPL", top_n=0)["error"]
