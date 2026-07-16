# Plan: Per-factor portfolio-integration notebooks + multi-factor notebook realignment

**Companion plan:** `docs/plans/factor-usage-section.md` in `dream-faster/unravel-router` — the factsheet section on factors.aperiodic.io that links to these notebooks.
**Land order:** this PR merges **before** the web PR (the factsheet links to `notebooks/portfolio_integration_<id>.ipynb` on `main`; shipping the web side first produces 404 links). Independent of unravel-router PR #742.

## Goal

Give every factor a short, runnable notebook answering *"How do I add this factor to my existing portfolio?"*, and make the existing multi-factor notebook the canonical answer to *"How do I build a portfolio from scratch?"*:

1. **New generated family** `notebooks/portfolio_integration_<id>.ipynb` — one per single factor (14) plus `portfolio_integration_composite-7.ipynb`. Fetches the factor's published portfolio returns, blends them with an existing book (user-supplied CSV or a built-in demo book), and reports correlation and before/after performance.
2. **`00_multi_factor_portfolio_construction.ipynb`** — update its default `factors` list to the 7 Factor Composite's constituents, so the notebook's out-of-the-box run literally reconstructs AF-COMP. Every factsheet links it as the "build from scratch" path.

Naming follows the existing `<topic>_<id>` convention (`factor_analysis_<id>`), echoes the `portfolio-40-returns` data naming, and sorts as one contiguous block after `factor_analysis_*` in the repo listing.

## 1. New `_INTEGRATION_TEMPLATE` in `scripts/generate_factor_notebooks.py`

A third jupytext percent-format template alongside `_FACTOR_TEMPLATE` / `_CORRELATION_TEMPLATE`. Format fields: `{name}`, `{id}`, `{factor_portfolios}` (repr'd list of portfolio slugs — `['<id>.40']` for singles, the 7 constituent slugs for the composite), `{sleeve_note}` (single- vs composite-specific sentence, see cell 8).

**The template is `.format()`-ed — every literal `{` `}` in Python code (dict comprehensions, f-strings) must be doubled `{{ }}`.**

### Cell outline (14 cells)

1. **md** — `# Adding {name} to an existing portfolio` + one-liner ("measures what a {name} sleeve does to a book you already run"); Top-40 / unlevered-1× note; *"Prerequisites: none — runs on the shared public demo key (preview data); set `APERIODIC_API_KEY` for full data."* (Mirrors the multi-factor notebook's cells 0–2, condensed. Licence: MIT.)
2. **code, `tags=["hide-input"]`** — the AUTO-GENERATED banner + inlined helpers: imports (`os`, `warnings`, `numpy`, `pandas`, `matplotlib.pyplot`, `dotenv`), `DEMO_API_KEY = "DEMO-KEY"` + `get_api_key()` (copy from `_FACTOR_TEMPLATE`), `perf_stats(returns) -> dict` (CAGR, annualized vol, Sharpe with √365, max drawdown), `plot_cumulative_and_drawdown(dict_of_series)` (two stacked axes).
3. **code** — pip cell for Colab/standalone self-containment: `import sys` + `!{{sys.executable}} -m pip install -q aperiodic-factors`. (The generated `factor_analysis_*` family has no pip cell because it assumes `requirements.txt`; this family targets prospects, so mirror the multi-factor notebook's pip cell. No alphalens needed.)
4. **md** — `### Parameters` bullet list: the API-key fallback ladder text (lift from multi-factor cell 6); `EXISTING_PORTFOLIO_RETURNS_CSV` — path/URL to a `date,return` daily CSV, `None` uses a synthetic demo book; `ALLOCATION` — fraction of the book moved to the sleeve; `START_DATE`.
5. **code** — parameter cell mirroring multi-factor cell 7's Colab-secret / `.env` / `DEMO-KEY` ladder, then:
   ```python
   FACTOR_PORTFOLIOS = {factor_portfolios}
   FACTOR_LABEL = "{name}"
   EXISTING_PORTFOLIO_RETURNS_CSV = None
   ALLOCATION = 0.20
   START_DATE = "2021-01-01"
   ```
   plus a params print.
6. **md** — `### Your existing portfolio` — supply your own daily return series, or fall back to a demo book: 60/40 BTC-ETH, buy-and-hold, rebalanced daily.
7. **code** — `if EXISTING_PORTFOLIO_RETURNS_CSV: pd.read_csv(..., index_col=0, parse_dates=True).squeeze()` else fetch `aperiodic.get_prices(...)` for BTC/ETH and compute `existing = (prices.pct_change() * [0.6, 0.4]).sum(axis=1)` (coerce numeric). Import idiom: `import aperiodic_factors as aperiodic`. **Verify the ticker symbol format against the SDK on first local run; if bare `["BTC", "ETH"]` differs, pick two ids from `get_tickers(...)` instead.**
8. **md** — `### The factor sleeve` — `{sleeve_note}`:
   - single: *"the published, unlevered (1×) daily returns of the {name} top-40 portfolio"*
   - composite: *"AF-COMP is reconstructed client-side as the equal-weight average of its seven constituents' published portfolio returns — the single-portfolio endpoint does not serve the composite directly"*
9. **code** —
   ```python
   parts = {{
       pid: pd.to_numeric(get_portfolio_returns(id=pid, api_key=APERIODIC_API_KEY), errors="coerce")
       for pid in FACTOR_PORTFOLIOS
   }}
   sleeve = pd.DataFrame(parts).mean(axis=1)
   ```
   (a single-element list degrades to identity), inner-join with `existing`, clip to `START_DATE`.
10. **md** — `### How the sleeve relates to your book`.
11. **code** — full-sample correlation print + 90-day rolling correlation plot (`axhline(0)`).
12. **md** — `### Before and after the blend`.
13. **code** — `blended = (1 - ALLOCATION) * existing + ALLOCATION * sleeve`; stats DataFrame with rows *Existing book / {name} sleeve / Blended ({{ALLOCATION:.0%}})* × CAGR / vol / Sharpe / max DD; then `plot_cumulative_and_drawdown(...)` for the three series.
14. **md** — closing: interpretation (*"a low or negative correlation is the point — the sleeve adds a return stream your book doesn't already own; most teams start at 10–25%"*), demo-key preview-data caveat, CTA links: create an account / generate an API key at factors.aperiodic.io, the factsheet `https://factors.aperiodic.io/catalog/{id}`, licensing → `https://factors.aperiodic.io/booking`. (Mirrors multi-factor cell 30's tone.)

Expected runtime per notebook: 1–7 `get_portfolio_returns` calls + one 2-ticker `get_prices` — seconds, not minutes.

## 2. Composite support in `scripts/factors_catalog.py`

`load_factors()` deliberately excludes composites, and the **deployed** catalog.json currently carries neither `type: "composite"` nor `constituents` (the web repo will start publishing them, but this PR lands first). Therefore:

- Add `constituents: tuple[str, ...] = ()` to the `Factor` dataclass.
- Add a hardcoded fallback with a comment pointing at `apps/factors/config/catalog.config.ts` in `dream-faster/unravel-router`:
  ```python
  _COMPOSITE_CONSTITUENTS = {
      "composite-7": (
          "momentum_enhanced", "carry_enhanced", "retail_flow", "margin_risk",
          "altair", "mean_reversion", "mean_reversion_enhanced",
      ),
  }
  ```
- New `load_composite_portfolios() -> list[Factor]`: builds `Factor`s from the *unfiltered* catalog entries matching `_is_composite`, taking constituents as `tuple(entry.get("constituents") or _COMPOSITE_CONSTITUENTS.get(entry["id"], ()))` — self-heals once the deployed catalog.json publishes the field. Skip (with a printed warning) any composite with no known constituents.
- **Do not touch `_factors()` / `load_factors()`** — factsheets, the README table, the correlation notebook and `factor_analysis_*` pruning must keep excluding composites.

## 3. Generator wiring in `scripts/generate_factor_notebooks.py`

- `write_scripts()`: for each single factor, also render `_INTEGRATION_TEMPLATE` → `notebooks/src/portfolio_integration_<id>.py`; for each composite from `load_composite_portfolios()`, render it with the constituent slugs as `{factor_portfolios}`. Include all new stems in the returned script list (that list feeds `prune_stale`'s keep-set — the composite stem must be in it or a full regen deletes the composite notebook).
- `prune_stale()`: add `portfolio_integration_*.ipynb` / `portfolio_integration_*.py` to the `managed` globs.
- `main()` argv validation currently checks ids against `load_factors()` only — extend to singles + composites so `python -m scripts.generate_factor_notebooks composite-7` works instead of failing as "Unknown factor id".
- Subset runs still rewrite the README table and correlation src on every invocation — harmless, expected in diffs.
- Redaction needs no changes: `--execute` redacts per notebook inside `process()`, and the workflow has a repo-wide redact step.

## 4. `00_multi_factor_portfolio_construction.ipynb` edit (hand-maintained — no src file)

- Param cell (cell 7): `factors = ["momentum_enhanced", "carry_enhanced", "retail_flow", "margin_risk", "altair", "mean_reversion", "mean_reversion_enhanced"]`.
- Add one framing sentence in the "Main Specification" markdown (cell 6) and in the intro (cell 2): *"The default parameters reconstruct the 7 Factor Composite (AF-COMP)."* Echo it briefly in the closing cell (cell 30).
- **Push the edit un-executed.** This PR touches `scripts/**`, which triggers `.github/workflows/generate-notebooks.yml` on the PR branch; the workflow executes everything (the multi-factor notebook has its own execution step) and commits the executed outputs back to the branch.

## 5. README

- `_factor_table()`: add a column **`Add to your portfolio`** → `[notebook](notebooks/portfolio_integration_{f.id}.ipynb)`. Use **repo-relative** links like the existing Notebook column — do not copy the absolute `GITHUB_RAW_BASE`/`GITHUB_BLOB_BASE` URLs, which still point at the repo's old `aperiodic-io/dataroom` name and survive only via GitHub's rename redirect.
- The table stays singles-only. Add a hand-written prose mention of `portfolio_integration_composite-7.ipynb` next to the existing Multi-Factor Portfolio Construction paragraph, and a short "Using a factor in your portfolio" intro sentence above the table linking both notebook kinds.

## 6. CI

No workflow changes. The new src files live under `notebooks/src/**` (a push trigger path), and generation/execution flows through the existing steps. ~15 additional light notebooks on 4 workers ≈ +3–8 minutes against a 120-minute timeout.

## 7. Verification

1. `python -m scripts.generate_factor_notebooks` (no `--execute`): expect 15 new `notebooks/src/portfolio_integration_*.py`, the README column, and **no pruning** of existing files. Inspect one generated src for un-doubled braces.
2. `python -m scripts.generate_factor_notebooks --execute polaris` with only the demo key in the environment — proves the notebook runs out of the box.
3. `python -m scripts.generate_factor_notebooks --execute composite-7` — proves the constituent-ensembling path (the composite must NOT call `get_portfolio_returns(id="composite-7.40")`, which 400s).
4. Optionally execute the multi-factor notebook locally (`jupyter nbconvert --to notebook --execute --inplace notebooks/00_multi_factor_portfolio_construction.ipynb`) if not delegating to CI.
5. `python -m scripts.redact_secrets notebooks/*.ipynb` as a no-op sanity check.
6. After merge: confirm `https://github.com/aperiodic-io/factors-dataroom/blob/main/notebooks/portfolio_integration_polaris.ipynb` renders — the web PR's link-check depends on it.

## Decisions & rationale (flip-able)

- **One shared "from scratch" notebook** instead of ~15 per-factor variants: the variants would differ only in the `factors` default, while each adds MBs of executed output regenerated weekly in CI. The factsheet compensates with factor-specific copy ("add `<id>` to the `factors` list…").
- **`portfolio_integration_<id>` naming** over `usage_*`/`integrate_*`: parallels `factor_analysis_<id>`, echoes `portfolio-40-returns`, sorts as a contiguous block. The hyphen in `portfolio_integration_composite-7` is harmless — jupytext reads the file; nothing imports it as a module.
- Commit convention: `feature(Notebooks): Add per-factor portfolio integration notebooks` / `chore(Notebooks): Realign multi-factor notebook defaults with AF-COMP`.
