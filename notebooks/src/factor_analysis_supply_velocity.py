# %%
# Install the packages this notebook needs. `pip install -r requirements.txt`
# (see the README) already does this for you; this cell makes the notebook
# self-contained if you're running it standalone (e.g. in Google Colab).
import sys

!{sys.executable} -m pip install -q aperiodic-factors alphalens-reloaded python-dotenv pandas

# %% tags=["hide-input"] jupyter={"source_hidden": true}
# AUTO-GENERATED from scripts/factors_catalog.py by
# scripts/generate_factor_notebooks.py -- do not edit by hand.
# --- Utility functions (inlined so this notebook is self-contained). ---
# This cell is collapsed by default when the notebook is rendered; expand it to
# see the helpers below.
import os
import warnings

import alphalens
import pandas as pd
from dotenv import load_dotenv

# The factors API serves preview data against a shared public demo key, so the
# notebook runs out-of-the-box with no signup. For full data the Aperiodic team
# provisions a key for you (factors.aperiodic.io/booking); once you have it,
# export APERIODIC_API_KEY (or set it in a .env file).
DEMO_API_KEY = "DEMO-KEY"


def get_api_key() -> str:
    try:
        load_dotenv()
    except Exception:  # noqa: BLE001
        warnings.warn("Could not load .env")  # noqa: B028
    return os.environ.get("APERIODIC_API_KEY") or DEMO_API_KEY


def factor_analysis(
    signal: pd.DataFrame, price: pd.DataFrame, max_loss: float = 1.0
) -> None:
    # The API can hand back object-dtype frames; AlphaLens' tear sheet then calls
    # np.sqrt on them and raises "loop of ufunc does not support argument 0 of
    # type int which has no callable sqrt method". Coerce to numeric first.
    signal = signal.apply(pd.to_numeric, errors="coerce")
    price = price.apply(pd.to_numeric, errors="coerce")
    # max_loss is AlphaLens' guard that raises when too much of the factor is
    # dropped in forward-return alignment + quantile binning. Restricting to the
    # dynamic universe legitimately drops a lot (90%+ for sparse long-only
    # factors), so default to 1.0 (never raise); AlphaLens still prints the exact
    # drop %, so the loss stays visible.
    factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
        signal.stack(), price, quantiles=5, max_loss=max_loss
    )
    alphalens.tears.create_full_tear_sheet(factor_data)


# %%
from aperiodic_factors import (
    get_historical_universe,
    get_portfolio_factors_historical,
    get_prices,
    get_tickers,
)

APERIODIC_API_KEY = get_api_key()

# Supply Velocity -- portfolio supply_velocity.40
portfolio = "supply_velocity"
universe_size = "40"

available_tickers = get_tickers(
    id=portfolio,
    api_key=APERIODIC_API_KEY,
    universe_size=universe_size,
    exchange=None,
)
historical_factors = get_portfolio_factors_historical(
    id=portfolio, tickers=available_tickers, api_key=APERIODIC_API_KEY
)
underlying = get_prices(tickers=available_tickers, api_key=APERIODIC_API_KEY)

# Mask the raw factor with the dynamic point-in-time universe (a boolean
# dates x tickers matrix) so AlphaLens scores only the universe we trade,
# not every ticker that was ever tradeable.
universe = get_historical_universe(
    size=universe_size,
    api_key=APERIODIC_API_KEY,
    start_date=str(historical_factors.index.min().date()),
    end_date=str(historical_factors.index.max().date()),
)
membership = (
    universe.reindex(index=historical_factors.index)
    .ffill()
    .reindex(columns=historical_factors.columns)
    .fillna(False)
    .astype(bool)
)
restricted_factors = historical_factors.where(membership)

columns_intersection = restricted_factors.columns.intersection(underlying.columns)
factor_analysis(restricted_factors[columns_intersection], underlying)

# %%
