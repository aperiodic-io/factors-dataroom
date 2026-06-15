"""Single-factor portfolio catalog for the data-room CSV/PDF exports.

The factor list and ALL narrative copy are sourced from the published catalog
bundle (`catalog.json`), which is the single source of truth maintained by the
Aperiodic web app. Nothing here is hand-maintained — if the catalog cannot be
loaded the run fails loudly rather than falling back to stale/local copy.

Source resolution (in priority order):
  1. `APERIODIC_FACTORS_CATALOG_FILE` — read a local JSON file (used for tests
     and sandboxed CI where egress is blocked).
  2. `APERIODIC_FACTORS_CATALOG_URL` — fetch from a custom URL.
  3. The default published URL (`https://factors.aperiodic.io/catalog.json`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
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

DEFAULT_CATALOG_URL = f"{SITE_BASE_URL}/catalog.json"
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
    """Load the raw catalog bundle from the configured local file or URL."""
    local_file = os.environ.get("APERIODIC_FACTORS_CATALOG_FILE")

    if local_file:
        path = Path(local_file)
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Failed to read factors catalog file at {path}: {exc}"
            ) from exc

    url = os.environ.get("APERIODIC_FACTORS_CATALOG_URL", DEFAULT_CATALOG_URL)

    try:
        response = requests.get(url, timeout=_CATALOG_FETCH_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(
            f"Failed to fetch factors catalog from {url}: {exc}"
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


@lru_cache(maxsize=1)
def _factors() -> tuple[Factor, ...]:
    return tuple(_build_factor(entry) for entry in _load_catalog())


def load_factors() -> list[Factor]:
    return list(_factors())


def find_factor(factor_id: str) -> Factor:
    for factor in _factors():
        if factor.id == factor_id:
            return factor
    raise KeyError(f"Unknown factor id: {factor_id}")
