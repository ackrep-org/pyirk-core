#!/usr/bin/env python3
"""
tools/perf_benchmark.py — Phase-0 performance benchmark harness for pyirk-core.

One command produces a compact metric table on stdout:
    ~/venvs/pyirk-core-venv/bin/python tools/perf_benchmark.py [--reps N] [--skip-ocse] [--skip-profile]

cProfile note: absolute times from cProfile are distorted (typically 3–5× slower than
wall-clock). Only relative function rankings are meaningful; wall-clock numbers in
sections (i)–(iii) are the authoritative baseline.

Dependencies: stdlib only (subprocess, time, timeit, cProfile, argparse, tempfile, textwrap).
"""

import argparse
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

# ── constants ────────────────────────────────────────────────────────────────
# Default venv lives under ~/venvs (NOT /tmp — systemd-tmpfiles silently removes
# aged files there); override via PYIRK_BENCH_VENV.
_VENV = os.environ.get("PYIRK_BENCH_VENV", str(Path.home() / "venvs/pyirk-core-venv"))
PYIRK_PYTHON = f"{_VENV}/bin/python"
PYIRK_PYTEST = f"{_VENV}/bin/pytest"
OCSE_DIR = Path.home() / "projekte/irk-data/ocse"
OCSE_TESTS = OCSE_DIR / "tests"

# Scales for synthetic benchmark
SYNTH_SCALES = [1_000, 5_000, 10_000]
# Number of full-item read passes in query benchmark
QUERY_REPS = 3

# ── helpers ──────────────────────────────────────────────────────────────────

def _run(cmd, env=None, cwd=None, timeout=600):
    """Run *cmd* list and return (returncode, stdout, stderr, elapsed_s)."""
    t0 = time.perf_counter()
    r = subprocess.run(
        cmd, capture_output=True, text=True,
        env=env, cwd=str(cwd) if cwd else None, timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr, time.perf_counter() - t0


def _run_file(script_text, env=None, timeout=600):
    """Write *script_text* to a temp file and run it with PYIRK_PYTHON."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(script_text)
        fpath = f.name
    try:
        return _run([PYIRK_PYTHON, fpath], env=env, timeout=timeout)
    finally:
        os.unlink(fpath)


def _base_env(extra=None):
    """Return environment suitable for pyirk subprocesses."""
    e = os.environ.copy()
    e["PATH"] = f"{_VENV}/bin:{e.get('PATH', '')}"
    if extra:
        e.update(extra)
    return e


def _fmt(seconds):
    if seconds is None:
        return "    N/A"
    if seconds >= 10:
        return f"{seconds:7.1f} s"
    return f"{seconds:7.3f} s"


# ── (i) OCSE module load time ────────────────────────────────────────────────

_LOAD_SCRIPT = textwrap.dedent("""\
    import time, os, sys
    import pyirk as p

    cc_flag = os.environ.get("PYIRK_DISABLE_CONSISTENCY_CHECKING", "").lower() != "true"
    if cc_flag:
        p.cc.enable_consistency_checking()

    ocse_dir = {ocse_dir!r}
    t0 = time.perf_counter()
    p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "agents1.py"), prefix="ag")
    p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "math1.py"),   prefix="ma", reuse_loaded=True)
    p.irkloader.load_mod_from_path(
        os.path.join(ocse_dir, "control_theory1.py"), prefix="ct", reuse_loaded=True
    )
    print(f"{{time.perf_counter()-t0:.4f}}")
""")


def measure_load_times(n_reps: int, ocse_missing: bool):
    results = {}
    if ocse_missing:
        results["load_cc_on"] = None
        results["load_cc_off"] = None
        return results

    script = _LOAD_SCRIPT.format(ocse_dir=str(OCSE_DIR))

    for cc_on in (True, False):
        label = "load_cc_on" if cc_on else "load_cc_off"
        extra = {} if cc_on else {"PYIRK_DISABLE_CONSISTENCY_CHECKING": "true"}
        times = []
        for _ in range(n_reps):
            rc, out, err, _ = _run_file(script, env=_base_env(extra))
            if rc != 0:
                print(f"  [WARN] load subprocess failed (cc_on={cc_on}):\n{err[:500]}", file=sys.stderr)
                times.append(None)
            else:
                try:
                    times.append(float(out.strip().splitlines()[-1]))
                except (ValueError, IndexError):
                    times.append(None)
        valid = [t for t in times if t is not None]
        results[label] = min(valid) if valid else None

    return results


# ── (ii) OCSE pytest times ───────────────────────────────────────────────────

def measure_pytest_times(n_reps: int, ocse_missing: bool):
    results = {}
    if ocse_missing:
        for k in ("suite_total", "test_e01", "test_c07"):
            results[k] = None
        return results

    suite_times = []
    for _ in range(n_reps):
        rc, out, err, elapsed = _run(
            [PYIRK_PYTHON, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"],
            env=_base_env(),
            cwd=OCSE_TESTS,
        )
        suite_times.append(elapsed)
    results["suite_total"] = min(suite_times)

    for key, pattern in [
        ("test_e01", "test_e01__element_type_rule"),
        ("test_c07", "test_c07__cc_theorem_application"),
    ]:
        times = []
        for _ in range(n_reps):
            rc, out, err, elapsed = _run(
                [PYIRK_PYTHON, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider", "-k", pattern],
                env=_base_env(),
                cwd=OCSE_TESTS,
            )
            times.append(elapsed)
        results[key] = min(times)

    return results


# ── (iii) synthetic module ────────────────────────────────────────────────────
#
# create_item() uses frame inspection to derive the variable name as the key_str.
# When called inside a loop we must supply key_str explicitly (the variable
# name on the LHS of the assignment would just be "itm").
# The base item also gets an explicit key_str so its variable name ("base_cls")
# never reaches the key-parser.

_SYNTH_SCRIPT = textwrap.dedent("""\
    import time, sys
    import pyirk as p

    __URI__ = "irk:/benchmark/synthetic{seed}"
    N = {n_items}
    km = p.KeyManager(keyseed={seed})
    p.register_mod(__URI__, km)
    p.start_mod(__URI__)

    base_cls = p.create_item(
        key_str="I0",
        R1__has_label="SyntheticBase",
        R4__is_instance_of=p.I2["Metaclass"],
    )

    # creation benchmark
    t0 = time.perf_counter()
    items = []
    for i in range(N):
        if i % 2 == 0:
            itm = p.create_item(
                key_str=f"I{{i+1}}",
                R1__has_label=f"SynClass{{i}}",
                R3__is_subclass_of=base_cls,
            )
        else:
            itm = p.create_item(
                key_str=f"I{{i+1}}",
                R1__has_label=f"SynInst{{i}}",
                R4__is_instance_of=base_cls,
            )
        items.append(itm)
    t_create = time.perf_counter() - t0

    p.end_mod()

    # query benchmark: read R3/R4 via __getattr__ (the hot path from the profile doc)
    t0 = time.perf_counter()
    for _rep in range({query_reps}):
        for i, itm in enumerate(items):
            if i % 2 == 0:
                _ = itm.R3__is_subclass_of
            else:
                _ = itm.R4__is_instance_of
    t_query = time.perf_counter() - t0

    print(f"create={{t_create:.4f}}")
    print(f"query={{t_query:.4f}}")
""")


def measure_synthetic(n_reps: int):
    results = {}
    for n in SYNTH_SCALES:
        seed = n  # use scale as seed so URIs are distinct across runs
        script = _SYNTH_SCRIPT.format(n_items=n, seed=seed, query_reps=QUERY_REPS)
        create_times, query_times = [], []
        for _ in range(n_reps):
            rc, out, err, _ = _run_file(script, env=_base_env())
            if rc != 0:
                print(f"  [WARN] synthetic(n={n}) failed:\n{err[:500]}", file=sys.stderr)
                create_times.append(None)
                query_times.append(None)
                continue
            vals = {}
            for line in out.strip().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    vals[k.strip()] = float(v.strip())
            create_times.append(vals.get("create"))
            query_times.append(vals.get("query"))
        valid_c = [t for t in create_times if t is not None]
        valid_q = [t for t in query_times if t is not None]
        results[f"synth_{n}_create"] = min(valid_c) if valid_c else None
        results[f"synth_{n}_query"] = min(valid_q) if valid_q else None
    return results


# ── (iv) cProfile ─────────────────────────────────────────────────────────────

_PROFILE_SCRIPT = textwrap.dedent("""\
    import cProfile, pstats, io, sys
    import pyirk as p

    __URI__ = "irk:/benchmark/profile0"
    N = {n_items}

    km = p.KeyManager(keyseed=77)
    p.register_mod(__URI__, km)
    p.start_mod(__URI__)
    base_cls = p.create_item(
        key_str="I0",
        R1__has_label="ProfBase",
        R4__is_instance_of=p.I2["Metaclass"],
    )

    def workload():
        items = []
        for i in range(N):
            if i % 2 == 0:
                itm = p.create_item(
                    key_str=f"I{{i+1}}",
                    R1__has_label=f"PC{{i}}",
                    R3__is_subclass_of=base_cls,
                )
            else:
                itm = p.create_item(
                    key_str=f"I{{i+1}}",
                    R1__has_label=f"PI{{i}}",
                    R4__is_instance_of=base_cls,
                )
            items.append(itm)
        p.end_mod()
        for _r in range(3):
            for i, itm in enumerate(items):
                if i % 2 == 0:
                    _ = itm.R3__is_subclass_of
                else:
                    _ = itm.R4__is_instance_of

    pr = cProfile.Profile()
    pr.enable()
    workload()
    pr.disable()

    buf = io.StringIO()
    for sort_key in ("tottime", "cumulative"):
        # do NOT call strip_dirs() — that removes "pyirk" from file paths,
        # breaking the filter below
        ps = pstats.Stats(pr, stream=buf)
        ps.sort_stats(sort_key)
        buf.write(f"\\n=== Top 15 by {{sort_key}} (pyirk frames only) ===\\n")
        ps.print_stats("pyirk", 15)

    print(buf.getvalue())
""")


def run_cprofile(n_items: int = 10_000):
    script = _PROFILE_SCRIPT.format(n_items=n_items)
    rc, out, err, _ = _run_file(script, env=_base_env(), timeout=300)
    if rc != 0:
        return f"[cProfile subprocess failed]\n{err[:800]}"
    return out


# ── table printing ────────────────────────────────────────────────────────────

def print_table(title, rows):
    print(f"\n{'─'*62}")
    print(f"  {title}")
    print(f"{'─'*62}")
    for label, val in rows:
        print(f"  {label:<44} {val}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="pyirk-core performance benchmark (Phase 0)")
    parser.add_argument("--reps", type=int, default=1,
                        help="measurement repetitions (best-of-N); default 1")
    parser.add_argument("--skip-ocse", action="store_true",
                        help="skip OCSE-dependent measurements")
    parser.add_argument("--skip-profile", action="store_true",
                        help="skip cProfile section")
    args = parser.parse_args()

    ocse_missing = not OCSE_DIR.exists() or args.skip_ocse
    if not OCSE_DIR.exists() and not args.skip_ocse:
        print(f"[WARN] OCSE not found at {OCSE_DIR} — skipping OCSE sections.", file=sys.stderr)

    print(f"\n{'═'*62}")
    print(f"  pyirk-core Performance Benchmark — Phase 0 Baseline")
    print(f"  Python : {PYIRK_PYTHON}")
    print(f"  reps   : {args.reps}")
    print(f"  OCSE   : {'missing/skipped' if ocse_missing else str(OCSE_DIR)}")
    print(f"{'═'*62}")

    # ── (i) load times ────────────────────────────────────────────────────────
    print("\n[i] Measuring OCSE module load times…", flush=True)
    load_res = measure_load_times(args.reps, ocse_missing)
    print_table("(i) OCSE module load  (agents1 + math1 + control_theory1)", [
        ("CC on  (default)",
         _fmt(load_res.get("load_cc_on"))),
        ("CC off (PYIRK_DISABLE_CONSISTENCY_CHECKING=true)",
         _fmt(load_res.get("load_cc_off"))),
    ])

    # ── (ii) pytest ───────────────────────────────────────────────────────────
    print("\n[ii] Running OCSE pytest suite…", flush=True)
    pytest_res = measure_pytest_times(args.reps, ocse_missing)
    print_table("(ii) OCSE pytest times  (CC on, wall-clock)", [
        ("test_package.py  — full suite",
         _fmt(pytest_res.get("suite_total"))),
        ("test_e01__element_type_rule",
         _fmt(pytest_res.get("test_e01"))),
        ("test_c07__cc_theorem_application",
         _fmt(pytest_res.get("test_c07"))),
    ])

    # ── (iii) synthetic ───────────────────────────────────────────────────────
    print("\n[iii] Running synthetic benchmarks…", flush=True)
    synth_res = measure_synthetic(args.reps)
    rows = []
    for n in SYNTH_SCALES:
        c = synth_res.get(f"synth_{n}_create")
        q = synth_res.get(f"synth_{n}_query")
        rows.append((f"{n:>6} items — create (R3+R4 mix)", _fmt(c)))
        rows.append((f"{n:>6} items — query  ({QUERY_REPS}× R3/R4 attr access)", _fmt(q)))
    print_table("(iii) Synthetic module (R3/R4 items, fresh subprocess each run)", rows)

    # ── (iv) cProfile ─────────────────────────────────────────────────────────
    if not args.skip_profile:
        print("\n[iv] Running cProfile on synthetic 10k workload…", flush=True)
        profile_out = run_cprofile(n_items=10_000)
        print(f"\n{'─'*62}")
        print("  (iv) cProfile — top 15 by tottime / cumtime (pyirk frames)")
        print("  Note: cProfile absolute times are distorted (3–5× slower).")
        print("        Use for relative hotspot ranking only.")
        print(f"{'─'*62}")
        print(profile_out)

    print(f"\n{'═'*62}")
    print("  Benchmark complete.")
    print(f"{'═'*62}\n")


if __name__ == "__main__":
    main()
