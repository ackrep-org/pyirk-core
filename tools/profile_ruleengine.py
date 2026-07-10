"""
cProfile wrapper for the pyirk rule engine.

Usage:
    ~/venvs/pyirk-core-venv/bin/python tools/profile_ruleengine.py

Profiles test_e01__element_type_rule (the longest OCSE test) and prints the
top-15 functions by cumulative time, with relative percentages.
"""

import cProfile
import pstats
import io
import subprocess
import sys
import os

PROF_OUT = "/tmp/ruleengine_prof.out"
TEST_DIR = os.path.expanduser("~/projekte/irk-data/ocse/tests/")
TEST_KEY = "test_e01__element_type_rule"
TOP_N = 15


def run_profile():
    result = subprocess.run(
        [
            sys.executable,
            "-m", "cProfile",
            "-o", PROF_OUT,
            "-m", "pytest",
            TEST_DIR,
            "-k", TEST_KEY,
            "-p", "no:randomly",
            "--tb=no",
            "-q",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout[-3000:])
    if result.stderr:
        print(result.stderr[-500:], file=sys.stderr)

    s = io.StringIO()
    ps = pstats.Stats(PROF_OUT, stream=s)
    ps.sort_stats("cumulative")
    ps.print_stats(TOP_N)
    raw = s.getvalue()
    print(raw)

    # compute relative percentages
    lines = raw.splitlines()
    total_cum = None
    entries = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 6 and parts[0].replace(",", "").isdigit():
            try:
                ncalls = parts[0].replace(",", "")
                cumtime = float(parts[3])
                if total_cum is None:
                    total_cum = cumtime
                func_label = " ".join(parts[5:])
                entries.append((ncalls, cumtime, func_label))
            except (ValueError, IndexError):
                pass

    if total_cum and total_cum > 0:
        print(f"\n{'Rang':<5} {'ncalls':<12} {'cumtime %':>10}  {'Funktion'}")
        print("-" * 80)
        for rank, (ncalls, cumtime, func_label) in enumerate(entries, start=1):
            pct = cumtime / total_cum * 100
            print(f"{rank:<5} {ncalls:<12} {pct:>9.1f}%  {func_label}")


if __name__ == "__main__":
    run_profile()
