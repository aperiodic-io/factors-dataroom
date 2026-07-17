"""Strip transient Jupyter notebook fields that create noisy diffs.

The factor notebooks are regenerated, re-executed against the live API, and
committed back on a schedule (see ``.github/workflows/generate-notebooks.yml``).
Every regeneration rewrites a handful of fields that carry no real information
but change on every run, so the executed-notebook diffs are dominated by churn
that hides the data/code changes an actual reviewer cares about:

* per-cell ``id`` -- jupytext assigns a fresh random id to every cell on each
  ``--to notebook`` conversion, so all ids change even when nothing else did;
* per-cell ``metadata.execution`` -- wall-clock timestamps nbconvert stamps on
  each cell as it runs;
* the kernel process id in ``/tmp/ipykernel_<pid>/<hash>.py`` paths -- IPython
  names each executed cell's temp module after the *kernel pid*, which is
  different on every run and leaks into warning/traceback output text. (The
  ``<hash>`` after it is derived from the cell source and is stable, so only the
  pid needs normalising.)

This normaliser removes the first two and normalises the third, while preserving
notebook source, outputs, execution counts, and every other metadata field. Run
it as the *final* step of the generation pipeline -- after execution and secret
redaction -- so nothing re-introduces the fields before the notebook is written.

    python -m scripts.clean_notebooks notebooks/            # a directory
    python -m scripts.clean_notebooks notebooks/foo.ipynb   # explicit files
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

# Per-cell ``metadata`` keys nbconvert writes on execution that change every run.
TRANSIENT_CELL_METADATA = ("execution",)

# ``/tmp/ipykernel_<pid>/<hash>.py`` -- normalise only the transient kernel pid,
# keeping the source-derived (stable) ``<hash>`` so genuine code changes still
# show up. Applied to cell outputs only; the string never appears in source.
_IPYKERNEL_PID = re.compile(r"ipykernel_\d+")
_IPYKERNEL_PLACEHOLDER = "ipykernel_<pid>"


def _normalise_output_text(obj: Any) -> Any:
    """Recursively replace the transient kernel pid in every string reachable
    from a cell's ``outputs`` (stream text, tracebacks, ``text/plain`` reprs)."""
    if isinstance(obj, str):
        return _IPYKERNEL_PID.sub(_IPYKERNEL_PLACEHOLDER, obj)
    if isinstance(obj, list):
        return [_normalise_output_text(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _normalise_output_text(value) for key, value in obj.items()}
    return obj


def clean_notebook(path: Path) -> bool:
    """Strip transient fields from a notebook in place.

    Returns True when the file content changed. Idempotent: a second run on an
    already-clean notebook is a no-op and returns False.
    """
    before = path.read_text(encoding="utf-8")
    notebook: dict[str, Any] = json.loads(before)

    for cell in notebook.get("cells", []):
        cell.pop("id", None)
        metadata = cell.get("metadata")
        if isinstance(metadata, dict):
            for key in TRANSIENT_CELL_METADATA:
                metadata.pop(key, None)
        outputs = cell.get("outputs")
        if isinstance(outputs, list):
            cell["outputs"] = _normalise_output_text(outputs)

    # Match the serialization redact_secrets / nbformat use (indent=1, a trailing
    # newline, non-ASCII preserved) so cleaning never reflows the whole file.
    after = json.dumps(notebook, indent=1, ensure_ascii=False) + "\n"
    if after != before:
        path.write_text(after, encoding="utf-8")
        return True
    return False


def iter_notebooks(paths: list[Path]) -> list[Path]:
    notebooks: list[Path] = []
    for path in paths:
        if path.is_dir():
            notebooks.extend(sorted(path.rglob("*.ipynb")))
        elif path.suffix == ".ipynb":
            notebooks.append(path)
    return notebooks


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Strip transient per-cell ids, execution timing metadata, and the "
            "kernel pid from notebook outputs so regenerated notebooks diff "
            "cleanly."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Notebook files or directories to clean.",
    )
    args = parser.parse_args(argv)

    changed = 0
    for notebook in iter_notebooks(args.paths):
        if clean_notebook(notebook):
            changed += 1
            print(f"cleaned {notebook}")

    print(f"Cleaned {changed} notebook(s).")


if __name__ == "__main__":
    main()
