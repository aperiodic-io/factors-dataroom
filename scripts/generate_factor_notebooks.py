"""Generate (and optionally execute) the factor notebooks from the catalog.

    python -m scripts.generate_factor_notebooks            # write + convert
    python -m scripts.generate_factor_notebooks --execute  # also run them
    python -m scripts.generate_factor_notebooks altair     # one factor

``--execute`` needs ``APERIODIC_API_KEY`` (wired from repo secrets in CI).
"""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.factors_catalog import (
    Factor,
    load_composite_portfolios,
    load_factors,
)
from scripts.redact_secrets import collect_secrets, redact_file

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
SRC_DIR = NOTEBOOKS_DIR / "src"
# 00_ prefix sorts the cross-factor overview above every factor_analysis_*.
CORRELATION_STEM = "00_factor_returns_correlation"

_GENERATED_BANNER = (
    "# AUTO-GENERATED from scripts/factors_catalog.py by\n"
    "# scripts/generate_factor_notebooks.py -- do not edit by hand.\n"
)

_FACTOR_TEMPLATE = '''# %% tags=["hide-input"] jupyter={{"source_hidden": true}}
{banner}
# --- Utility functions (inlined so this notebook is self-contained). ---
# This cell is collapsed by default when the notebook is rendered; expand it to
# see the helpers below.
import os
import warnings

import alphalens
import pandas as pd
from dotenv import load_dotenv

# The factors API serves preview data against a shared public demo key, so the
# notebook runs out-of-the-box with no signup. Export APERIODIC_API_KEY (or set
# it in a .env file) to query with your own key for full access.
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

# {name} -- portfolio {portfolio_id}
portfolio = "{id}"
universe_size = "{universe}"

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
'''

_CORRELATION_TEMPLATE = '''# %% tags=["hide-input"] jupyter={{"source_hidden": true}}
{banner}
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
returns = {{}}
for portfolio in portfolios:
    try:
        returns[portfolio] = get_portfolio_returns(
            id=portfolio, api_key=APERIODIC_API_KEY
        )
    except Exception as exc:  # noqa: BLE001
        print(f"skipping {{portfolio}}: {{exc}}")

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
    cbar_kws={{"shrink": 0.8}},
)
plt.title("Cross-Sectional Returns Correlation Matrix")
plt.tight_layout()
plt.show()

# %%
'''

# One-sentence description of the sleeve for cell 8, chosen per factor kind.
_SINGLE_SLEEVE_NOTE = (
    "The sleeve is the published, unlevered (1x) daily returns of the "
    "**{name}** top-40 portfolio."
)
_COMPOSITE_SLEEVE_NOTE = (
    "**{name}** is reconstructed client-side as the equal-weight average of its "
    "{count} constituents' published portfolio returns -- the single-portfolio "
    "endpoint does not serve the composite directly."
)

# "How do I add this factor to a portfolio I already run?" Fetches the factor's
# published portfolio returns (a composite ensembles its constituents), blends
# them with an existing book, and reports correlation + before/after stats.
# Targets prospects, so it carries its own pip cell (Colab / standalone).
#
# .format()-ed like the templates above: every literal brace in the code below
# is doubled; the only fields are {banner} {name} {id} {factor_portfolios}
# {sleeve_note}.
_INTEGRATION_TEMPLATE = '''# %% [markdown]
# # Adding {name} to an existing portfolio
#
# This notebook measures what a **{name}** sleeve does to a book you already
# run: how correlated the two are, and how the blend's risk and return compare
# before and after. Portfolios are the published **Top-40, unlevered (1x)**
# returns.
#
# **Prerequisites: none** -- runs on the shared public demo key (preview data);
# set `APERIODIC_API_KEY` for full data.
#
# Licence: MIT

# %%
# Install the notebook's full dependency closure first, so it is self-contained
# when run standalone (e.g. Google Colab). This must precede the collapsed
# helper cell below, whose imports (matplotlib / numpy / pandas / dotenv) would
# otherwise fail on a fresh environment. `pip install -r requirements.txt` (see
# the README) already covers this if you cloned the repo.
import sys

!{{sys.executable}} -m pip install -q aperiodic-factors python-dotenv matplotlib numpy pandas

# %% tags=["hide-input"] jupyter={{"source_hidden": true}}
{banner}
# --- Utility functions (inlined so this notebook is self-contained). ---
# This cell is collapsed by default when the notebook is rendered; expand it to
# see the helpers below.
import os
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# The factors API serves preview data against a shared public demo key, so the
# notebook runs out-of-the-box with no signup. Export APERIODIC_API_KEY (or set
# it in a .env file) to query with your own key for full access.
DEMO_API_KEY = "DEMO-KEY"


def get_api_key() -> str:
    try:
        load_dotenv()
    except Exception:  # noqa: BLE001
        warnings.warn("Could not load .env")  # noqa: B028
    return os.environ.get("APERIODIC_API_KEY") or DEMO_API_KEY


def perf_stats(returns: pd.Series) -> dict:
    # Headline stats for a daily return series: CAGR, annualized volatility,
    # Sharpe (sqrt(365) for daily crypto) and max drawdown.
    returns = pd.to_numeric(returns, errors="coerce").dropna()
    if returns.empty or returns.std() == 0:
        nan = float("nan")
        return {{"CAGR": nan, "Vol": nan, "Sharpe": nan, "Max drawdown": nan}}
    curve = (1 + returns).cumprod()
    years = len(returns) / 365
    cagr = curve.iloc[-1] ** (1 / years) - 1 if years > 0 else float("nan")
    vol = returns.std() * np.sqrt(365)
    sharpe = returns.mean() / returns.std() * np.sqrt(365)
    max_drawdown = (curve / curve.cummax() - 1).min()
    return {{"CAGR": cagr, "Vol": vol, "Sharpe": sharpe, "Max drawdown": max_drawdown}}


def plot_cumulative_and_drawdown(series_by_label: dict) -> None:
    # Two stacked panels: cumulative growth of 1 unit, and drawdown from peak.
    fig, (ax_cum, ax_dd) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True,
        gridspec_kw={{"height_ratios": [2, 1]}},
    )
    for label, series in series_by_label.items():
        curve = (1 + pd.to_numeric(series, errors="coerce").dropna()).cumprod()
        ax_cum.plot(curve.index, curve.values, label=label)
        ax_dd.plot(curve.index, (curve / curve.cummax() - 1).values, label=label)
    ax_cum.set_title("Cumulative growth of 1 unit")
    ax_cum.set_ylabel("Growth")
    ax_cum.legend()
    ax_dd.set_title("Drawdown")
    ax_dd.set_ylabel("Drawdown")
    ax_dd.axhline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    plt.show()

# %% [markdown]
# ### Parameters
#
# - **APERIODIC_API_KEY** -- optional. Falls back to a Google Colab secret, then
#   a local `.env` / environment variable, then the shared public **demo key**
#   (preview data), so the notebook runs as-is.
# - **FACTOR_PORTFOLIOS** -- the published portfolio slug(s) that make up the
#   sleeve: one for a single factor, the constituents for a composite.
# - **EXISTING_PORTFOLIO_RETURNS_CSV** -- path or URL to your own daily
#   `date,return` CSV. `None` blends against a synthetic demo book instead.
# - **ALLOCATION** -- the fraction of the book reallocated into the sleeve.
# - **START_DATE** -- earliest date to include.

# %%
# Resolve the API key with the same ladder as the multi-factor notebook: a Google
# Colab secret, then a local .env / environment variable, then the shared public
# demo key (preview data) so the notebook runs with no signup.
try:
    import google.colab

    IN_COLAB = True
except ImportError:
    IN_COLAB = False

if IN_COLAB:
    from google.colab import userdata

    try:
        APERIODIC_API_KEY = userdata.get("APERIODIC_API_KEY") or DEMO_API_KEY
    except Exception:  # noqa: BLE001 -- secret not set / access denied
        APERIODIC_API_KEY = DEMO_API_KEY
else:
    APERIODIC_API_KEY = get_api_key()

import aperiodic_factors as aperiodic
from aperiodic_factors import get_portfolio_returns

# Published portfolio slug(s) whose returns make up the factor sleeve. A single
# factor has one slug; a composite lists its constituents, ensembled below.
FACTOR_PORTFOLIOS = {factor_portfolios}
FACTOR_LABEL = "{name}"
# Your own daily return series (a `date,return` CSV). None -> synthetic demo book.
EXISTING_PORTFOLIO_RETURNS_CSV = None
# Fraction of the book reallocated into the factor sleeve.
ALLOCATION = 0.20
# Ignore history before this date.
START_DATE = "2021-01-01"

print("**Parameters:**")
print(f"FACTOR_PORTFOLIOS: {{FACTOR_PORTFOLIOS}}")
print(f"FACTOR_LABEL: {{FACTOR_LABEL}}")
print(f"EXISTING_PORTFOLIO_RETURNS_CSV: {{EXISTING_PORTFOLIO_RETURNS_CSV}}")
print(f"ALLOCATION: {{ALLOCATION}}")
print(f"START_DATE: {{START_DATE}}")

# %% [markdown]
# ### Your existing portfolio
#
# Supply your own daily return series via `EXISTING_PORTFOLIO_RETURNS_CSV` (a
# `date,return` CSV). Left as `None`, we fall back to a demo book: 60/40
# BTC-ETH, bought and held, rebalanced daily.

# %%
if EXISTING_PORTFOLIO_RETURNS_CSV:
    existing = pd.read_csv(
        EXISTING_PORTFOLIO_RETURNS_CSV, index_col=0, parse_dates=True
    ).squeeze("columns")
    existing = pd.to_numeric(existing, errors="coerce").dropna()
    existing.name = "Existing book"
else:
    # No book supplied -> synthesize a 60/40 BTC-ETH book, rebalanced daily,
    # from published close prices. A pandas Series of weights aligns by ticker
    # label, so the column order the API returns does not matter.
    DEMO_WEIGHTS = pd.Series({{"BTC": 0.6, "ETH": 0.4}})
    prices = aperiodic.get_prices(
        tickers=list(DEMO_WEIGHTS.index),
        api_key=APERIODIC_API_KEY,
        start_date=START_DATE,
    )
    asset_returns = (
        prices.reindex(columns=DEMO_WEIGHTS.index)
        .apply(pd.to_numeric, errors="coerce")
        .pct_change()
    )
    # min_count so a day missing a ticker (or the first, price-less day) stays
    # NaN and is dropped, rather than silently collapsing to a reweighted book.
    existing = (
        (asset_returns * DEMO_WEIGHTS)
        .sum(axis=1, min_count=len(DEMO_WEIGHTS))
        .dropna()
    )
    existing.name = "Existing book (demo 60/40 BTC-ETH)"

existing = existing[existing.index >= pd.Timestamp(START_DATE)]
print(
    f"Existing book: {{len(existing)}} daily returns "
    f"({{existing.index.min().date()}} to {{existing.index.max().date()}})"
)

# %% [markdown]
# ### The factor sleeve
#
# {sleeve_note}

# %%
# Fetch each constituent portfolio's published returns and equal-weight them.
# For a single factor FACTOR_PORTFOLIOS holds one slug, so this reduces to that
# factor's own returns.
parts = {{
    pid: pd.to_numeric(
        get_portfolio_returns(id=pid, api_key=APERIODIC_API_KEY), errors="coerce"
    )
    for pid in FACTOR_PORTFOLIOS
}}
# dropna() before the mean so the sleeve only spans dates where *every*
# constituent has published returns; otherwise a partial row would silently
# become an equal-weight average of fewer factors than advertised.
sleeve = pd.DataFrame(parts).dropna().mean(axis=1)
sleeve.name = FACTOR_LABEL

# Inner-join the sleeve to the book on their shared trading days, then clip to
# START_DATE so every comparison below spans the same window.
aligned = pd.concat({{"existing": existing, "sleeve": sleeve}}, axis=1).dropna()
aligned = aligned[aligned.index >= pd.Timestamp(START_DATE)]
existing_aligned = aligned["existing"]
sleeve_aligned = aligned["sleeve"]
print(
    f"Aligned sample: {{len(aligned)}} shared trading days "
    f"({{aligned.index.min().date()}} to {{aligned.index.max().date()}})"
)

# %% [markdown]
# ### How the sleeve relates to your book
#
# The full-sample correlation and its 90-day rolling version. A low or negative
# correlation means the sleeve carries a return stream your book does not
# already own.

# %%
correlation = existing_aligned.corr(sleeve_aligned)
print(
    f"Full-sample correlation ({{FACTOR_LABEL}} sleeve vs your book): {{correlation:.3f}}"
)

rolling_correlation = existing_aligned.rolling(90).corr(sleeve_aligned)
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(rolling_correlation.index, rolling_correlation.values)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_title(f"90-day rolling correlation: {{FACTOR_LABEL}} sleeve vs your book")
ax.set_ylabel("Correlation")
fig.tight_layout()
plt.show()

# %% [markdown]
# ### Before and after the blend
#
# Reallocating `ALLOCATION` of the book into the sleeve, then comparing the
# blended series against the original on CAGR, volatility, Sharpe and max
# drawdown.

# %%
blended = (1 - ALLOCATION) * existing_aligned + ALLOCATION * sleeve_aligned

stats = pd.DataFrame(
    {{
        "Existing book": perf_stats(existing_aligned),
        f"{{FACTOR_LABEL}} sleeve": perf_stats(sleeve_aligned),
        f"Blended ({{ALLOCATION:.0%}})": perf_stats(blended),
    }}
).T[["CAGR", "Vol", "Sharpe", "Max drawdown"]]
print(stats.to_string(float_format=lambda x: f"{{x:,.4f}}"))

plot_cumulative_and_drawdown(
    {{
        "Existing book": existing_aligned,
        f"{{FACTOR_LABEL}} sleeve": sleeve_aligned,
        f"Blended ({{ALLOCATION:.0%}})": blended,
    }}
)

# %% [markdown]
# ### Takeaways
#
# A low or negative correlation is the point -- the sleeve adds a return stream
# your book doesn't already own. Most teams start at a **10-25%** allocation and
# size from there.
#
# The committed copy of this notebook is rendered against the full dataset. Run
# it yourself and it works out of the box on the shared public **demo key**,
# which serves **preview data**; sign up for a key to work with the full history.
#
# - Create an account and generate an API key at
#   [factors.aperiodic.io](https://factors.aperiodic.io)
# - This factor's factsheet:
#   [factors.aperiodic.io/catalog/{id}](https://factors.aperiodic.io/catalog/{id})
# - Licensing & data access:
#   [factors.aperiodic.io/booking](https://factors.aperiodic.io/booking)
'''


def _write(path: Path, content: str) -> None:
    path.write_text(content)
    print(f"  wrote {path.relative_to(REPO_ROOT)}")


README = REPO_ROOT / "README.md"
_TABLE_BEGIN = "<!-- BEGIN FACTOR TABLE"
_TABLE_END = "<!-- END FACTOR TABLE -->"


def _factor_table(factors: list[Factor]) -> str:
    rows = "\n".join(
        f"| [{f.name}]({f.detail_url}) "
        f"| [PDF](factsheets/{f.id}.pdf) "
        f"| [notebook](notebooks/factor_analysis_{f.id}.ipynb) "
        f"| [notebook](notebooks/portfolio_integration_{f.id}.ipynb) "
        f"| [CSV]({f.factor_data_csv_url}) "
        f"| [CSV]({f.returns_csv_url}) |"
        for f in factors
    )
    # Repo-relative links (like the Notebook column) -- not the absolute
    # GITHUB_BLOB_BASE, which still points at the repo's old `dataroom` name.
    return (
        "| Factor | Factsheet | Notebook | Add to your portfolio "
        "| Raw factor data | Portfolio returns |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{rows}"
    )


def update_root_readme(factors: list[Factor]) -> None:
    text = README.read_text()
    begin_eol = text.index("\n", text.index(_TABLE_BEGIN)) + 1
    end = text.index(_TABLE_END, begin_eol)
    README.write_text(text[:begin_eol] + _factor_table(factors) + "\n" + text[end:])
    print("  updated README.md factor table")


def _write_integration_script(
    factor: Factor, factor_portfolios: list[str], sleeve_note: str
) -> Path:
    """Render one portfolio-integration notebook src and return its path."""
    path = SRC_DIR / f"portfolio_integration_{factor.id}.py"
    _write(
        path,
        _INTEGRATION_TEMPLATE.format(
            banner=_GENERATED_BANNER.rstrip(),
            name=factor.name,
            id=factor.id,
            factor_portfolios=repr(factor_portfolios),
            sleeve_note=sleeve_note,
        ),
    )
    return path


def write_scripts(factors: list[Factor], composites: list[Factor]) -> list[Path]:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for factor in factors:
        # AlphaLens factor-analysis notebook ("how does this factor behave?").
        path = SRC_DIR / f"factor_analysis_{factor.id}.py"
        _write(
            path,
            _FACTOR_TEMPLATE.format(
                banner=_GENERATED_BANNER.rstrip(),
                name=factor.name,
                portfolio_id=factor.portfolio_id,
                id=factor.id,
                universe=factor.default_universe,
            ),
        )
        written.append(path)

        # Portfolio-integration notebook ("how do I add it to my book?"). A
        # single factor's sleeve is just its own published portfolio.
        written.append(
            _write_integration_script(
                factor,
                factor_portfolios=[factor.portfolio_id],
                sleeve_note=_SINGLE_SLEEVE_NOTE.format(name=factor.name),
            )
        )

    # Composite portfolios get an integration notebook only: the sleeve is the
    # equal-weight ensemble of the constituents' published returns (the single-
    # portfolio endpoint does not serve a composite slug). Resolve constituent
    # ids to slugs against the full single-factor catalog, not any argv subset.
    slug_by_id = {f.id: f.portfolio_id for f in load_factors()}
    for composite in composites:
        # load_composite_portfolios() already validated the constituents; fail
        # loudly on any residual miss rather than silently shipping a partial
        # composite (or, on a full regen, pruning its externally-linked notebook).
        missing = [c for c in composite.constituents if c not in slug_by_id]
        if missing:
            raise SystemExit(
                f"composite {composite.id!r}: constituents absent from catalog: "
                f"{sorted(missing)}"
            )
        constituent_slugs = [slug_by_id[c] for c in composite.constituents]
        written.append(
            _write_integration_script(
                composite,
                factor_portfolios=constituent_slugs,
                sleeve_note=_COMPOSITE_SLEEVE_NOTE.format(
                    name=composite.name, count=len(constituent_slugs)
                ),
            )
        )

    # The correlation notebook and the README table always cover the full
    # catalog, regardless of any per-factor subset passed on argv.
    corr_path = SRC_DIR / f"{CORRELATION_STEM}.py"
    _write(
        corr_path,
        _CORRELATION_TEMPLATE.format(
            banner=_GENERATED_BANNER.rstrip(),
        ),
    )
    written.append(corr_path)

    update_root_readme(load_factors())
    return written


def prune_stale(keep: set[str]) -> None:
    """Delete managed notebooks no longer in the catalog (e.g. blacklisted),
    so a full regen is authoritative. Only touches files we generate."""
    managed = list(NOTEBOOKS_DIR.glob("factor_analysis_*.ipynb"))
    managed += list(SRC_DIR.glob("factor_analysis_*.py"))
    managed += list(NOTEBOOKS_DIR.glob("portfolio_integration_*.ipynb"))
    managed += list(SRC_DIR.glob("portfolio_integration_*.py"))
    managed += [NOTEBOOKS_DIR / f"{CORRELATION_STEM}.ipynb"]
    managed += [SRC_DIR / f"{CORRELATION_STEM}.py"]
    for path in managed:
        if path.exists() and path.stem not in keep:
            path.unlink()
            print(f"  pruned {path.relative_to(REPO_ROOT)}")


# Gitignored; uploaded as a CI artefact so it never lands in notebooks/.
CI_ARTIFACTS = REPO_ROOT / "ci-artifacts"
LOGS_DIR = CI_ARTIFACTS / "execution_logs"
REPORT = CI_ARTIFACTS / "execution_report.md"


def _job_count(default: int = 4) -> int:
    raw = os.environ.get("NOTEBOOK_JOBS", "").strip()
    if not raw:
        return default
    try:
        return max(int(raw), 1)
    except ValueError:
        return default


def _run(cmd: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


def process(py_file: Path, do_execute: bool) -> tuple[str, bool, str]:
    """Convert (and optionally execute) one notebook. Never raises; output is
    aggregated into the report so a failing CI run stays diagnosable."""
    stem = py_file.stem
    ipynb = NOTEBOOKS_DIR / f"{stem}.ipynb"

    ok, output = _run(
        ["jupytext", "--to", "notebook", "--output", str(ipynb), str(py_file)]
    )
    if not ok:
        return stem, False, output
    if not do_execute:
        print(f"  converted {ipynb.name}")
        return stem, True, ""

    print(f"  converting + executing {ipynb.name} ...")
    ok, output = _run(
        [
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
            # jupytext does not embed a kernelspec, so pin one explicitly.
            "--ExecutePreprocessor.kernel_name=python3",
            "--ExecutePreprocessor.timeout=1800",
            str(ipynb),
        ]
    )
    if not ok:
        (LOGS_DIR / f"{stem}.log").write_text(output)
        print(f"  FAILED {stem} -- see ci-artifacts/execution_logs/{stem}.log")
        return stem, ok, output

    # Strip any secret the live API key could have left in an output (a stray
    # traceback, repr, etc.) before the notebook is committed. Done here, in the
    # generator, so it also covers local `--execute` runs, not just CI.
    secrets = collect_secrets()
    if secrets:
        redacted = redact_file(str(ipynb), secrets)
        if redacted:
            print(f"  redacted {redacted} secret occurrence(s) from {ipynb.name}")
    print(f"  OK {stem}")
    return stem, ok, output


def main(argv: list[str]) -> None:
    do_execute = "--execute" in argv
    wanted = [a for a in argv if not a.startswith("--")]

    factors = load_factors()
    composites = load_composite_portfolios()
    if wanted:
        wanted_set = set(wanted)
        selected_factors = [f for f in factors if f.id in wanted_set]
        selected_composites = [c for c in composites if c.id in wanted_set]
        known = {f.id for f in selected_factors} | {c.id for c in selected_composites}
        missing = wanted_set - known
        if missing:
            raise SystemExit(f"Unknown factor ids: {sorted(missing)}")
        factors = selected_factors
        composites = selected_composites

    print(
        f"Generating notebooks for {len(factors)} factor(s) "
        f"and {len(composites)} composite(s):"
    )
    scripts = write_scripts(factors, composites)

    if not wanted:  # full regen is authoritative -- drop anything stale
        prune_stale({p.stem for p in scripts})

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    jobs = min(_job_count(), len(scripts))
    verb = "Converting + executing" if do_execute else "Converting"
    print(f"{verb} {len(scripts)} notebook(s) with {jobs} worker(s):")

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda p: process(p, do_execute), scripts))

    failures = [
        (stem, "\n".join(out.strip().splitlines()[-60:]))
        for stem, ok, out in sorted(results)
        if not ok
    ]

    if do_execute:
        lines = [
            "# Notebook execution report",
            "",
            f"Total: {len(results)} | "
            f"Passed: {len(results) - len(failures)} | "
            f"Failed: {len(failures)}",
            "",
        ]
        for name, tail in failures:
            lines += [f"## {name}", "", "```", tail, "```", ""]
        REPORT.write_text("\n".join(lines) + "\n")
        print(f"Wrote {REPORT.relative_to(REPO_ROOT)}")

    if failures:
        raise SystemExit(
            f"{len(failures)} notebook(s) failed: {[n for n, _ in failures]}"
        )

    print("Done.")


if __name__ == "__main__":
    main(sys.argv[1:])
