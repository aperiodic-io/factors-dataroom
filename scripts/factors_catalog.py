"""Single-factor portfolio catalog for the data-room CSV/PDF exports.

The factor list and ALL narrative copy are sourced from the published catalog
bundle at `https://factors.aperiodic.io/catalog.json`, which is the single
source of truth maintained by the Aperiodic web app. There is no override and
nothing here is hand-maintained — if the catalog cannot be fetched the run
fails loudly rather than falling back to any local/stale copy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_BASE_URL = "https://factors.aperiodic.io"
BOOKING_URL = f"{SITE_BASE_URL}/booking"

GITHUB_BLOB_BASE = "https://github.com/aperiodic-io/dataroom/blob/main"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/aperiodic-io/dataroom/main"
# Factors without a committed factor_analysis_<id>.ipynb fall back to this.
_GENERIC_NOTEBOOK = "notebooks/00_factor_returns_correlation.ipynb"

CATALOG_URL = f"{SITE_BASE_URL}/catalog.json"
_CATALOG_FETCH_TIMEOUT = 30


@dataclass(frozen=True)
class Factor:
    id: str
    name: str
    portfolio_id: str
    default_universe: str
    short_description: str
    long_description: str
    effect: str = ""
    # Constituent factor ids, for composite portfolios only (empty for singles).
    constituents: tuple[str, ...] = ()

    @property
    def detail_url(self) -> str:
        return (
            f"{SITE_BASE_URL}/portfolio/{self.portfolio_id}"
            "?exchange=unconstrained"
        )

    @property
    def returns_csv_url(self) -> str:
        return f"{GITHUB_RAW_BASE}/data/portfolio-40-returns/{self.id}.csv"

    @property
    def factor_data_csv_url(self) -> str:
        return f"{GITHUB_RAW_BASE}/data/raw-factors/{self.id}.csv"

    @property
    def has_factor_notebook(self) -> bool:
        return (
            REPO_ROOT / "notebooks" / f"factor_analysis_{self.id}.ipynb"
        ).exists()

    @property
    def notebook_url(self) -> str:
        name = (
            f"notebooks/factor_analysis_{self.id}.ipynb"
            if self.has_factor_notebook
            else _GENERIC_NOTEBOOK
        )
        return f"{GITHUB_BLOB_BASE}/{name}"


def _read_catalog_bundle() -> dict:
    """Fetch the raw catalog bundle from the published URL — the single source
    of truth, with no override."""
    try:
        response = requests.get(CATALOG_URL, timeout=_CATALOG_FETCH_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(
            f"Failed to fetch factors catalog from {CATALOG_URL}: {exc}"
        ) from exc


def _load_catalog() -> list[dict]:
    """Return the list of factor dicts from the published catalog bundle."""
    bundle = _read_catalog_bundle()

    try:
        factors = bundle["catalog"]["factors"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "Factors catalog bundle is missing 'catalog.factors'"
        ) from exc

    if not isinstance(factors, list) or not factors:
        raise RuntimeError("Factors catalog contains no factors")

    return factors


def _build_factor(entry: dict) -> Factor:
    slug = entry["slug"]

    return Factor(
        id=entry["id"],
        name=entry["name"],
        portfolio_id=slug,
        default_universe=slug.split(".")[-1],
        short_description=entry["description"],
        long_description=entry["longDescription"],
        # catalog.json has no `effect`; leave EMPTY so callers fall back to the
        # catalog short description rather than inventing a marketing hook.
        effect="",
    )


# Composite portfolios (e.g. "composite-7" / "7 Factor Composite") are blends of
# several cross-sectional factors, not single factors -- the single-factor
# portfolio API does not serve them (get_tickers 400s "Incorrect portfolio id").
# They are excluded from the single-factor data room (notebooks, factsheets,
# README). Detected by name/id marker since catalog.json has no explicit kind.
_COMPOSITE_MARKER = "composite"


def _is_composite(factor: Factor) -> bool:
    return (
        _COMPOSITE_MARKER in factor.id.lower()
        or _COMPOSITE_MARKER in factor.name.lower()
    )


# The deployed catalog.json does not yet publish a composite's constituent
# factors, so map them here as a fallback until it does. Keep in sync with
# `apps/factors/config/catalog.config.ts` in `dream-faster/unravel-router`.
# `load_composite_portfolios()` prefers a `constituents` field on the catalog
# entry when present, so this table self-heals once the web app publishes it.
_COMPOSITE_CONSTITUENTS: dict[str, tuple[str, ...]] = {
    "composite-7": (
        "momentum_enhanced",
        "carry_enhanced",
        "retail_flow",
        "margin_risk",
        "altair",
        "mean_reversion",
        "mean_reversion_enhanced",
    ),
}


@lru_cache(maxsize=1)
def _factors() -> tuple[Factor, ...]:
    return tuple(
        factor
        for factor in (_build_factor(entry) for entry in _load_catalog())
        if not _is_composite(factor)
    )


def load_factors() -> list[Factor]:
    return list(_factors())


def load_composite_portfolios() -> list[Factor]:
    """Composite portfolios (e.g. the 7 Factor Composite), which ``load_factors``
    deliberately excludes.

    Each returned ``Factor`` carries its ``constituents`` (single-factor ids) so
    callers can reconstruct the composite client-side from those factors'
    published portfolio returns -- the single-portfolio API does not serve a
    composite slug directly (``get_portfolio_returns(id="composite-7.40")`` 400s).

    Constituents come from the catalog entry's ``constituents`` field when it is
    published, otherwise from the ``_COMPOSITE_CONSTITUENTS`` fallback. A
    composite with no known constituents is skipped with a warning.
    """
    composites: list[Factor] = []
    for entry in _load_catalog():
        factor = _build_factor(entry)
        if not _is_composite(factor):
            continue
        constituents = tuple(
            entry.get("constituents") or _COMPOSITE_CONSTITUENTS.get(factor.id, ())
        )
        if not constituents:
            print(
                f"  skipping composite {factor.id!r}: no known constituents "
                "(add them to _COMPOSITE_CONSTITUENTS or publish them in catalog.json)"
            )
            continue
        composites.append(replace(factor, constituents=constituents))
    return composites


def find_factor(factor_id: str) -> Factor:
    for factor in _factors():
        if factor.id == factor_id:
            return factor
    raise KeyError(f"Unknown factor id: {factor_id}")
