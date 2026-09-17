"""Shared helpers for the result checks: strict JSON loading, tolerant comparison and a uniform runner."""

import json
import math
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from pipeline.common import RESULTS, TYPE_NODES_PATH


class Skip(Exception):
    """Raised by a check whose inputs are legitimately absent."""


def reject_constant(name: str):
    raise ValueError(f"non-finite value {name}")


def read_json(path: Path):
    """Parse a JSON file, failing on NaN or Infinity."""
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def result_json(name: str):
    return read_json(RESULTS / name)


def result_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(RESULTS / name)


def result_text(name: str) -> str:
    return (RESULTS / name).read_text(encoding="utf-8")


def data_available() -> bool:
    """Whether the local neuPrint cache the graph is built from is on disk."""
    return TYPE_NODES_PATH.exists()


def close(a, b, rel: float = 1e-6, abs_tol: float = 1e-9) -> bool:
    """Tolerant equality for numbers, None and nested lists or dicts of them."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], rel, abs_tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y, rel, abs_tol) for x, y in zip(a, b))
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return a == b
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=abs_tol)


def first_difference(a, b, rel: float = 1e-6, abs_tol: float = 1e-9, path: str = "") -> str | None:
    """Location and values of the first mismatch between two nested structures under :func:`close`, or None."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f"{path or 'top level'}: keys differ ({sorted(set(a) ^ set(b))})"
        for key in a:
            found = first_difference(a[key], b[key], rel, abs_tol, f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            found = first_difference(x, y, rel, abs_tol, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if close(a, b, rel, abs_tol) else f"{path}: {a!r} vs {b!r}"


def same_text(actual: str, expected: str) -> bool:
    """Equality of two documents up to line endings and trailing whitespace."""
    def normalize(text: str) -> str:
        return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n"))

    return normalize(actual) == normalize(expected)


def run(check: Callable[[], str]) -> None:
    """Run ``check``, print one OK, SKIP or FAIL line, and exit non-zero on failure.

    Parameters: ``check`` returns a one-line summary on success, raises :class:`Skip` when its inputs are
    absent, and raises any other exception on failure.
    """
    try:
        summary = check()
    except Skip as skip:
        print(f"SKIP: {skip}")
        return
    except AssertionError as error:
        print(f"FAIL: {error}")
        sys.exit(1)
    except Exception as error:  # noqa: BLE001
        print(f"FAIL: {type(error).__name__}: {error}")
        sys.exit(1)
    print(f"OK: {summary}")
