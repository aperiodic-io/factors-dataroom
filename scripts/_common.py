"""Shared helpers for the export / factsheet pipeline."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from scripts.factors_catalog import Factor, load_factors

if TYPE_CHECKING:
    import pandas as pd


# The Aperiodic Factors backend reports portfolio returns at 2x leverage
# (200% gross exposure — 100% long / 100% short). The data room publishes
# unlevered, 1x returns, so every return series fetched from the API is
# divided by this factor before it is exported to CSV or charted on a
# factsheet. Keeping the adjustment here gives it a single source of truth.
BACKEND_LEVERAGE = 2.0


def get_unlevered_portfolio_returns(*, id: str, api_key: str) -> "pd.Series":
    """Fetch a portfolio's daily returns and rescale them from the backend's
    2x leverage down to 1x (see ``BACKEND_LEVERAGE``). Also drops a trailing
    incomplete (current-day) observation so the series ends on the last
    complete UTC day, matching the apps/alpha portfolio page."""
    from aperiodic import get_portfolio_returns

    returns = get_portfolio_returns(id=id, api_key=api_key) / BACKEND_LEVERAGE
    return drop_incomplete_last_day(returns)


def get_api_key() -> str:
    key = os.environ.get("APERIODIC_API_KEY")
    if not key:
        raise RuntimeError("APERIODIC_API_KEY environment variable is not set")
    return key


def drop_incomplete_last_day(returns: "pd.Series") -> "pd.Series":
    """Drop a trailing same-day (incomplete) observation so the series ends on
    the last *complete* UTC day.

    import pandas as pd

    if returns.empty:
        return returns
    last_date = pd.Timestamp(returns.index[-1]).date()
    today_utc = pd.Timestamp.now(tz="UTC").date()
    if last_date == today_utc:
        return returns.iloc[:-1]
    return returns


class UnknownFactors(KeyError):
    """Raised by select_factors() when argv names ids not in the catalog."""


def select_factors(argv: list[str]) -> list[Factor]:
    """Every catalog factor, or just the subset named in argv."""
    factors = load_factors()
    if not argv:
        return factors
    wanted = set(argv)
    selected = [f for f in factors if f.id in wanted]
    missing = wanted - {f.id for f in selected}
    if missing:
        raise UnknownFactors(sorted(missing))
    return selected


def job_count(default: int = 4) -> int:
    """Parallel worker count (override via FACTSHEET_JOBS). Conservative
    default — the work is dominated by Aperiodic Factors API round-trips."""
    raw = os.environ.get("FACTSHEET_JOBS", "").strip()
    if not raw:
        return default
    try:
        n = int(raw)
    except ValueError:
        return default
    return max(n, 1)
