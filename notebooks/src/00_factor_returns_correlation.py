# %% tags=["hide-input"] jupyter={"source_hidden": true}
# AUTO-GENERATED from scripts/factors_catalog.py by
# scripts/generate_factor_notebooks.py -- do not edit by hand.
# --- Utility functions (inlined so this notebook is self-contained). ---
# This cell is collapsed by default when the notebook is rendered; expand it to
# see the helpers below.
import os
import warnings

import requests
from dotenv import load_dotenv

# The factors API serves preview data against a shared public demo key, so the
# notebook runs out-of-the-box with no signup. Export APERIODIC_API_KEY (or set
# it in a .env file) to query with your own key for full access.
DEMO_API_KEY = "DEMO-KEY"
CATALOG_URL = "https://factors.aperiodic.io/catalog.json"


def get_api_key() -> str:
    try:
        load_dotenv()
    except Exception:  # noqa: BLE001
        warnings.warn("Could not load .env")  # noqa: B028
    return os.environ.get("APERIODIC_API_KEY") or DEMO_API_KEY


def load_portfolio_ids() -> list[str]:
    # The published catalog bundle is the single source of truth for the factor
    # list; fetch it directly so the notebook needs nothing else from the repo.
    bundle = requests.get(CATALOG_URL, timeout=30).json()
    return [factor["slug"] for factor in bundle["catalog"]["factors"]]


# %%
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from aperiodic_factors import get_portfolio_returns

APERIODIC_API_KEY = get_api_key()

portfolios = load_portfolio_ids()

# Fetch each portfolio's returns, skipping any the API can't serve yet (e.g. a
# brand-new factor with no published returns) so one bad id doesn't sink the
# whole heatmap.
returns = {}
for portfolio in portfolios:
    try:
        returns[portfolio] = get_portfolio_returns(
            id=portfolio, api_key=APERIODIC_API_KEY
        )
    except Exception as exc:  # noqa: BLE001
        print(f"skipping {portfolio}: {exc}")

# Coerce to numeric so object-dtype series from the API don't make .corr() raise.
returns_df = pd.DataFrame(returns).apply(pd.to_numeric, errors="coerce")

# %%

correlation_matrix = returns_df.corr()

plt.figure(figsize=(16, 13))
sns.heatmap(
    correlation_matrix,
    annot=True,
    cmap="coolwarm",
    center=0,
    square=True,
    fmt=".2f",
    cbar_kws={"shrink": 0.8},
)
plt.title("Cross-Sectional Returns Correlation Matrix")
plt.tight_layout()
plt.show()

# %%
