"""Redact configured secret values from notebook outputs before committing.

CI executes notebooks against the live API and commits the rendered copy back.
An executed notebook could, in principle, capture a secret in an output (a stray
traceback, an accidental print, a repr). This scrubs every occurrence of the
secrets named in ``SECRET_ENV_VARS`` (read from the environment) out of the
given notebooks, replacing them with a placeholder, so rendered notebooks can be
committed safely.

It never prints the secret values themselves -- only counts and the file names.

    python -m scripts.redact_secrets notebooks/foo.ipynb [more.ipynb ...]
"""

from __future__ import annotations

import json
import os
import sys

# Secrets that CI puts in the environment and that must never reach a committed
# notebook. Add to this list if more secrets are ever wired into a notebook run.
SECRET_ENV_VARS = (
    "APERIODIC_API_KEY",
    "CF_ACCESS_CLIENT_ID",
    "CF_ACCESS_CLIENT_SECRET",
)
PLACEHOLDER = "***REDACTED***"
MIN_LEN = 8  # ignore trivially short / empty values so we never over-redact


def _collect_secrets() -> list[str]:
    secrets: list[str] = []
    for var in SECRET_ENV_VARS:
        val = os.environ.get(var, "")
        if val and len(val) >= MIN_LEN and val not in secrets:
            secrets.append(val)
    return secrets


def _scrub(obj, secrets: list[str]):
    """Recursively replace secret substrings in every string in the structure.

    Operating on decoded strings (not the raw file) means JSON escaping can't
    hide a secret from us.
    """
    if isinstance(obj, str):
        for s in secrets:
            if s in obj:
                obj = obj.replace(s, PLACEHOLDER)
        return obj
    if isinstance(obj, list):
        return [_scrub(x, secrets) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub(v, secrets) for k, v in obj.items()}
    return obj


def redact_file(path: str, secrets: list[str]) -> int:
    """Redact secrets in one notebook in place; return the number redacted."""
    try:
        with open(path, encoding="utf-8") as f:
            nb = json.load(f)
    except FileNotFoundError:
        print(f"redact_secrets: skipping missing file {path}")
        return 0

    before = json.dumps(nb, ensure_ascii=False)
    nb = _scrub(nb, secrets)
    after = json.dumps(nb, ensure_ascii=False)
    if before == after:
        return 0

    n = after.count(PLACEHOLDER) - before.count(PLACEHOLDER)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return n


def main(argv: list[str]) -> int:
    secrets = _collect_secrets()
    if not secrets:
        print("redact_secrets: no secrets configured in the environment; nothing to do.")
        return 0

    total = 0
    for path in argv:
        n = redact_file(path, secrets)
        if n:
            print(f"redact_secrets: redacted {n} occurrence(s) in {path}")
            total += n

    if total:
        # Surface the leak loudly so it gets investigated -- but never echo the value.
        print(f"::warning::redact_secrets removed {total} secret occurrence(s) from notebooks")
    else:
        print("redact_secrets: no secret occurrences found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
