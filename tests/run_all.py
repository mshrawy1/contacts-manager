# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Run every test file and print an overall summary.

Usage:

    python tests/run_all.py

or double-click run_tests.bat.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The tests print Arabic, and this runner reprints it. Its own output
# stream still follows the console codepage, which on an Arabic Windows
# is cp1256 -- and cp1256 has no Arabic-Indic digits, so one "٠" in a
# test would kill the whole run. The test files fix their own stream in
# _harness.setup(); this fixes the runner's.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# How long one test file may take before it is treated as stuck. The
# slowest of them finishes in well under a minute on an ordinary machine,
# so five is generous even for a loaded build server, while still being
# short enough that a hang is reported rather than waited out.
FILE_TIMEOUT = 300

# Simplest first, so a break in the foundations shows up immediately.
FILES = [
    "test_models.py",
    "test_i18n.py",
    "test_settings.py",
    "test_icons.py",
    "test_theme.py",
    "test_vcf.py",
    "test_csv.py",
    "test_store.py",
    "test_xlsx.py",
    "test_ui.py",
]


def main() -> int:
    results: list[tuple[str, bool]] = []

    for name in FILES:
        path = HERE / name
        if not path.exists():
            print(f"!! missing test file: {name}")
            results.append((name, False))
            continue

        print("=" * 64)
        print(f"  {name}")
        print("=" * 64)

        try:
            process = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=FILE_TIMEOUT,
            )
        except subprocess.TimeoutExpired as expired:
            # A test file that hangs used to hang this runner with it, in
            # silence, for as long as anybody was willing to wait -- and
            # on a build server that means burning the job's whole time
            # limit before reporting nothing at all. Waiting for a fixed
            # while and then saying plainly which file stopped is worth
            # far more than waiting for ever.
            for stream in (expired.stdout, expired.stderr):
                if stream:
                    text = stream if isinstance(stream, str) else stream.decode(
                        "utf-8", errors="replace")
                    print(text, end="")
            print(f"\n!! {name} was still running after {FILE_TIMEOUT} seconds "
                  f"and was stopped.\n")
            results.append((name, False))
            continue

        print(process.stdout, end="")
        if process.stderr.strip():
            print("--- errors ---")
            print(process.stderr, end="")
        print()
        results.append((name, process.returncode == 0))

    print("=" * 64)
    print("  Overall summary")
    print("=" * 64)
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")

    failed = [name for name, passed in results if not passed]
    print()
    if failed:
        print(f"{len(failed)} test files failed.")
        return 1
    print(f"All {len(results)} test files passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
