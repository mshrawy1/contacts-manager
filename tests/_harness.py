# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Shared helpers for the test files.

The tests are plain Python with no external libraries, so they run on any
machine that has Python without installing anything extra.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_failures: list[str] = []
_total = 0


def setup() -> None:
    """Make the app package importable and allow non-ASCII output."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def check(label: str, condition: bool, extra: object = "") -> None:
    """Record the result of one test and print it."""
    global _total
    _total += 1
    if not condition:
        _failures.append(label)
    mark = "PASS  " if condition else "FAIL  "
    suffix = f"  -> {extra}" if extra != "" else ""
    print(mark + label + suffix)


def finish(title: str) -> int:
    """Print the summary and return the right exit code."""
    print()
    if _failures:
        print(f"{title}: {len(_failures)} of {_total} failed")
        for name in _failures:
            print("  - " + name)
        return 1
    print(f"{title}: all {_total} checks passed")
    return 0
