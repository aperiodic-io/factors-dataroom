"""Factor-analysis JSON export for the sales deck.

Writes ``data/factor-analysis/<id>.json`` from the SAME AlphaLens-clean frame
the factsheet's page 2 renders, so the published numbers are identical by
construction:

- ``meanReturnByQuantile`` — alphalens ``mean_return_by_quantile`` (demeaned),
  converted to the per-shortest-period rate exactly like
  ``page_two._plot_mean_return_by_quantile`` (fractional returns; consumers
  multiply by 1e4 for bps).
- ``quantileDailyReturns`` — ``page_two._quantile_daily_returns`` verbatim
  (per-date / per-quantile mean demeaned forward returns; consumers compound
  them like AlphaLens' ``cumulative_returns``).
- ``ic`` — the daily Spearman information coefficient for the same period
  ``page_two._plot_ic_with_stats`` charts.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import alphalens
import pandas as pd

from scripts.factors_catalog import Factor
from scripts.factsheet.page_two import _forward_return_period, _quantile_daily_returns

ANALYSIS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "factor-analysis"


def _clean_float(value: float) -> float | None:
    return None if value is None or math.isnan(value) else round(float(value), 10)


def _series_payload(s: pd.Series) -> dict:
    s = s.dropna()
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in s.index],
        "values": [_clean_float(v) for v in s.to_numpy()],
    }


def write_analysis_json(factor: Factor, clean: pd.DataFrame) -> Path:
    """Export the page-2 analysis inputs for one factor; returns the path."""
    period = _forward_return_period(clean)

    # Quantile bars — overall mean demeaned forward return per quantile,
    # rated to the shortest period so 1D/5D/10D are comparable (page-2 math).
    mean_q, _ = alphalens.performance.mean_return_by_quantile(
        clean, by_date=False, demeaned=True
    )
    mean_q = mean_q.apply(
        alphalens.utils.rate_of_return, axis=0, base_period=mean_q.columns[0]
    )
    mean_by_period = {
        str(col): [_clean_float(v) for v in mean_q[col].sort_index().to_numpy()]
        for col in mean_q.columns
    }

    # Cumulative-by-quantile inputs — per-date mean demeaned forward returns.
    by_q, _ = _quantile_daily_returns(clean)
    by_q = by_q.dropna(how="all")
    quantile_daily = {
        "dates": [d.strftime("%Y-%m-%d") for d in by_q.index],
        **{
            f"q{int(q)}": [_clean_float(v) for v in by_q[q].to_numpy()]
            for q in sorted(by_q.columns)
        },
    }

    # Daily IC (Spearman) for the same period.
    ic = alphalens.performance.factor_information_coefficient(clean)[period]

    payload = {
        "id": factor.id,
        "universe": factor.default_universe,
        "asOf": str(by_q.index[-1].date()) if len(by_q.index) else None,
        "quantiles": int(mean_q.index.max()),
        "periods": [str(c) for c in mean_q.columns],
        "period": period,
        "meanReturnByQuantile": mean_by_period,
        "quantileDailyReturns": quantile_daily,
        "ic": _series_payload(ic),
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / f"{factor.id}.json"
    out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return out
