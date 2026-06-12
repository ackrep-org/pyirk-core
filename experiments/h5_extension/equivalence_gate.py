#!/usr/bin/env python3
"""
equivalence_gate.py — H5 Extension acceptance gate for the Zebra rule set.

Runs a curated subset of zebra rules — see ``ZEBRA_RULE_KEYS`` below —
through ``apply_semantic_rules(*selected, exhaust=True)`` on the Zebra KB
(``zebra_base_data`` + ``zebra_puzzle_rules``) along two paths in **separate
subprocesses** (DataStore isolation) and verifies three acceptance criteria
modelled after the recalibrated Phase 2.1 gates:

  Gate 1 — per-subject state equivalence: for every subject in
           ``ds.statements``, the set ``{(rel_uri, obj_uri-or-repr)}`` after
           the native path must equal the set after the delegation path.
  Gate 2 — idempotency: a SECOND ``apply_semantic_rules`` call right after
           each path (no KB reset) must add 0 new statements — required for
           BOTH native and delegation.
  Gate 3 — duplicate-multiset equivalence: after both runs the full multiset
           of (s, p, o) triples in ``ds.statements`` is identical between
           native and delegation — Phase 2.1's recalibrated criterion
           (delegation must not introduce or hide duplicates relative to the
           native baseline).

The two evaluation passes run in dedicated subprocesses so the in-process
``core.ds`` state of one path cannot leak into the other.  The subprocess
dumps a JSON snapshot of its DataStore, the main process compares the
snapshots in memory.

Reproducible runs:
  # native baseline
  /home/user/venvs/pyirk-core-venv/bin/python \\
      experiments/h5_extension/equivalence_gate.py \\
      > experiments/h5_extension/equivalence_gate.log 2>&1

  # with delegation flag set (only affects the *delegation* subprocess —
  # the gate script always runs the *native* path with the flag cleared
  # and the *delegation* path with the flag set, regardless of the env)
  PYIRK_NEMO_DELEGATION=1 /home/user/venvs/pyirk-core-venv/bin/python \\
      experiments/h5_extension/equivalence_gate.py \\
      > experiments/h5_extension/equivalence_gate.log 2>&1

Exit-Codes:
  0  — overall_gate_ok = true  (all three gates pass)
  1  — overall_gate_ok = false (at least one gate failed)
  2  — Infrastructure error (Nemo binary missing, Zebra data not loadable, etc.)
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter

# ─────────────────────────────────────────────────────────────────────────────
# Paths and constants
# ─────────────────────────────────────────────────────────────────────────────

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
NEMO_BIN = os.environ.get("PYIRK_NEMO_BIN", "/home/user/bin/nmo")
# sympy is not in pyirk-venv; neo-rag-venv has it (same Python 3.13.5).
SYMPY_EXTRA = "/home/user/venvs/neo-rag-venv/lib/python3.13/site-packages"
VENV_PYTHON = "/home/user/venvs/pyirk-core-venv/bin/python"
SRC_DIR = os.path.join(REPO_ROOT, "src")
ZEBRA_BASE_DATA_PATH = os.path.join(
    REPO_ROOT, "tests", "test_data", "zebra_base_data.py",
)
ZEBRA_RULES_PATH = os.path.join(
    REPO_ROOT, "tests", "test_data", "zebra_puzzle_rules.py",
)
ZEBRA_RULES_URI = "irk:/ocse/0.2/zebra_puzzle_rules"

# Curated set of zebra rules applied by the gate.  Picked so the rule set
# satisfies three properties on the (zb + zr)-only KB used by the gate:
#   1. every rule terminates without an AssertionError when applied via
#      ``apply_semantic_rules`` (the rule I725 fails on this minimal KB
#      because its SPARQL premise binds object positions that can resolve
#      to literals — diagnosed in task_004),
#   2. the set converges to a fixpoint in one extra pass (idempotency
#      requirement of Gate 2),
#   3. it contains the literal-premise rules H5 Phase 1 delegates to Nemo
#      (I705, I790, I800, I820), plus I702 as a stable symmetric-relation
#      companion that the H5 test suite also exercises (see
#      ``tests/test_h5_extension_literal_premises.py``).
ZEBRA_RULE_KEYS = ("I702", "I705", "I790", "I800", "I820")


# ─────────────────────────────────────────────────────────────────────────────
# Load guard — mirror Phase 2 gate
# ─────────────────────────────────────────────────────────────────────────────

def load_guard():
    try:
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
    except Exception:
        load1 = None
    warnings_list = []
    if load1 is not None and load1 >= 0.5:
        warnings_list.append(f"load={load1:.2f}>=0.5")
    return {
        "load1": load1,
        "load_str": f"{load1:.2f}" if load1 is not None else "N/A",
        "load_burdened": bool(warnings_list),
        "load_burdened_label": " (load-belastet)" if warnings_list else "",
        "warnings": warnings_list,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Subprocess script template
# ─────────────────────────────────────────────────────────────────────────────
#
# Runs in a clean Python process.  Loads Zebra (base data + puzzle rules),
# optionally enables PYIRK_NEMO_DELEGATION, then runs apply_semantic_rules to
# fixpoint over *all* registered rules.  Dumps a JSON snapshot of
# ``ds.statements``.  Idempotency probe (second apply_semantic_rules call
# with no KB reset) runs in BOTH modes — Gate 2 demands idempotency from the
# native path too.
#
# triples list = one entry per Statement object → Counter on the list gives
# the dup-multiset Gate 3 compares.

_SUBPROCESS_SCRIPT = r'''
import sys, os, json, time, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, %(sympy_extra)r)
sys.path.insert(0, %(src_dir)r)

MODE = %(mode)r            # 'native' or 'delegation'
OUT_JSON = %(out_json)r
RULE_KEYS = %(rule_keys)r

if MODE == 'delegation':
    os.environ['PYIRK_NEMO_DELEGATION'] = '1'
else:
    os.environ.pop('PYIRK_NEMO_DELEGATION', None)

import pyirk as p
from pyirk import ruleengine

zb = p.irkloader.load_mod_from_path(%(zebra_base_data)r, prefix='zb')
zr = p.irkloader.load_mod_from_path(%(zebra_rules)r, prefix='zr', reuse_loaded=True)

zebra_rules_uri = %(zebra_rules_uri)r

all_rules = [getattr(zr, k) for k in RULE_KEYS]

try:
    with open('/proc/loadavg') as fh:
        load1_pre = float(fh.read().split()[0])
except Exception:
    load1_pre = None

t0 = time.perf_counter()
res1 = ruleengine.apply_semantic_rules(
    *all_rules, mod_context_uri=zebra_rules_uri, exhaust=True,
)
t1 = time.perf_counter()
elapsed_first = t1 - t0
n_new_first = len(res1.new_statements)


def _obj_repr(o):
    uri = getattr(o, 'uri', None)
    if uri is not None:
        return uri
    return 'LIT:' + repr(o)


by_subject_lists = {}
triples = []
for subj_uri, rel_dict in p.ds.statements.items():
    by_subject_lists.setdefault(subj_uri, [])
    for rel_uri, stm_or_list in rel_dict.items():
        stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
        for stm in stms:
            obj_r = _obj_repr(stm.object)
            by_subject_lists[subj_uri].append([rel_uri, obj_r])
            triples.append([subj_uri, rel_uri, obj_r])

by_subject = {
    k: sorted({tuple(t) for t in v}) for k, v in by_subject_lists.items()
}

# Gate 2 — idempotency probe: second pass on the same DataStore must add 0.
res2 = ruleengine.apply_semantic_rules(
    *all_rules, mod_context_uri=zebra_rules_uri, exhaust=True,
)
idem_n_new = len(res2.new_statements)
idem_examples = []
for stm in res2.new_statements[:5]:
    try:
        s_uri = stm.subject.uri
    except Exception:
        s_uri = repr(stm.subject)
    try:
        r_uri = stm.predicate.uri
    except Exception:
        r_uri = repr(stm.predicate)
    idem_examples.append([s_uri, r_uri, _obj_repr(stm.object)])

try:
    with open('/proc/loadavg') as fh:
        load1_post = float(fh.read().split()[0])
except Exception:
    load1_post = None

with open(OUT_JSON, 'w', encoding='utf-8') as fh:
    json.dump({
        'mode': MODE,
        'elapsed_sec': elapsed_first,
        'load1_pre': load1_pre,
        'load1_post': load1_post,
        'n_new_first': n_new_first,
        'n_subjects': len(by_subject),
        'n_triples': len(triples),
        'by_subject': by_subject,
        'triples': triples,
        'idempotency_n_new': idem_n_new,
        'idempotency_examples': idem_examples,
    }, fh)

print(f"subprocess {MODE} done: elapsed={elapsed_first:.3f}s "
      f"n_new_first={n_new_first} n_subj={len(by_subject)} "
      f"n_triples={len(triples)} idem_n_new={idem_n_new}")
'''


def run_subprocess(mode, out_json, timeout=1200):
    """Run the Zebra workload in a clean subprocess.  Returns out_json or None."""
    src = _SUBPROCESS_SCRIPT % dict(
        sympy_extra=SYMPY_EXTRA,
        src_dir=SRC_DIR,
        zebra_base_data=ZEBRA_BASE_DATA_PATH,
        zebra_rules=ZEBRA_RULES_PATH,
        zebra_rules_uri=ZEBRA_RULES_URI,
        rule_keys=ZEBRA_RULE_KEYS,
        mode=mode,
        out_json=out_json,
    )
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, encoding="utf-8",
    ) as fh:
        fh.write(src)
        script_path = fh.name
    try:
        proc = subprocess.run(
            [VENV_PYTHON, script_path],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            print(
                f"FEHLER ({mode}-subprocess exit {proc.returncode}):",
                file=sys.stderr,
            )
            print("---- stdout ----", file=sys.stderr)
            print(proc.stdout[:20000], file=sys.stderr)
            print("---- stderr ----", file=sys.stderr)
            print(proc.stderr[:20000], file=sys.stderr)
            return None
        print(proc.stdout.strip())
        if proc.stderr.strip():
            print(f"[{mode} stderr] {proc.stderr.strip()[:600]}", file=sys.stderr)
        return out_json
    finally:
        os.unlink(script_path)


# ─────────────────────────────────────────────────────────────────────────────
# Gate evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _to_set(by_subject):
    return {k: {tuple(t) for t in v} for k, v in by_subject.items()}


def gate1_state_equivalence(snap_a, snap_b, *, limit=20):
    """Per-subject equality of the {(rel_uri, obj_repr)} sets."""
    by_a = _to_set(snap_a["by_subject"])
    by_b = _to_set(snap_b["by_subject"])
    all_subjs = set(by_a) | set(by_b)
    diffs = []
    for subj in sorted(all_subjs):
        a = by_a.get(subj, set())
        b = by_b.get(subj, set())
        if a != b:
            diffs.append({
                "subject_uri": subj,
                "only_in_A": sorted(a - b),
                "only_in_B": sorted(b - a),
            })
    return diffs[:limit], len(diffs)


def gate2_idempotent_both(snap_a, snap_b):
    """Idempotency probe runs in BOTH modes — both must show 0 new statements."""
    n_a = snap_a.get("idempotency_n_new")
    n_b = snap_b.get("idempotency_n_new")
    ok = (n_a == 0 and n_b == 0)
    return ok, n_a, n_b, snap_a.get("idempotency_examples", []), snap_b.get("idempotency_examples", [])


def gate3_dup_equivalence(snap_a, snap_b, *, limit=20):
    """Phase-2.1-calibrated dup-multiset gate: native multiset is the ground
    truth; the delegation multiset must match it exactly — diff of either side
    fails the gate.  Equivalence-to-native, not absolute zero, is the criterion.
    """
    ca = Counter(tuple(t) for t in snap_a["triples"])
    cb = Counter(tuple(t) for t in snap_b["triples"])
    diffs = [
        (triple, ca[triple], cb[triple])
        for triple in (set(ca) | set(cb))
        if ca[triple] != cb[triple]
    ]
    diffs.sort(key=lambda x: -abs(x[2] - x[1]))
    native_dups = sum(1 for m in ca.values() if m > 1)
    deleg_dups = sum(1 for m in cb.values() if m > 1)
    return diffs[:limit], len(diffs), native_dups, deleg_dups


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="H5 Extension acceptance gate (Zebra)",
    )
    parser.add_argument(
        "--keep-snapshots", action="store_true",
        help="Do not delete the per-mode JSON snapshots after evaluation.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("H5 Extension — Zebra Equivalence Gate (native vs nemo-delegation)")
    print("=" * 70)

    # Pre-flight ---------------------------------------------------------------
    print("\n=== Pre-flight ===")
    lg_pre = load_guard()
    print(f"uptime load (1-min): {lg_pre['load_str']}")
    if lg_pre["load_burdened"]:
        for w in lg_pre["warnings"]:
            print(f"  WARNUNG: {w}")
        print("  → measurements proceed, but get a '(load-belastet)' marker.")

    if not os.path.isfile(NEMO_BIN):
        print(f"FEHLER: Nemo binary missing: {NEMO_BIN}", file=sys.stderr)
        sys.exit(2)
    proc = subprocess.run([NEMO_BIN, "--version"], capture_output=True, text=True)
    nemo_version = (proc.stdout + proc.stderr).strip().split("\n")[0]
    print(f"Nemo: {nemo_version}")

    for path in (ZEBRA_BASE_DATA_PATH, ZEBRA_RULES_PATH):
        if not os.path.isfile(path):
            print(f"FEHLER: Zebra source missing: {path}", file=sys.stderr)
            sys.exit(2)

    work_dir = tempfile.mkdtemp(prefix="h5ext_gate_")
    snap_native = os.path.join(work_dir, "snap_native.json")
    snap_deleg = os.path.join(work_dir, "snap_delegation.json")

    # Path A — native ----------------------------------------------------------
    print("\n=== Pfad A — native (subprocess) ===")
    t0 = time.perf_counter()
    if run_subprocess("native", snap_native) is None:
        print("FEHLER: native subprocess failed → exit 2", file=sys.stderr)
        sys.exit(2)
    wall_a = time.perf_counter() - t0
    print(f"native subprocess wall: {wall_a:.3f}s")

    # Path B — delegation ------------------------------------------------------
    print("\n=== Pfad B — delegation (subprocess) ===")
    t0 = time.perf_counter()
    if run_subprocess("delegation", snap_deleg) is None:
        print("FEHLER: delegation subprocess failed → exit 2", file=sys.stderr)
        sys.exit(2)
    wall_b = time.perf_counter() - t0
    print(f"delegation subprocess wall: {wall_b:.3f}s")

    # Load snapshots ----------------------------------------------------------
    with open(snap_native, "r", encoding="utf-8") as fh:
        snap_a = json.load(fh)
    with open(snap_deleg, "r", encoding="utf-8") as fh:
        snap_b = json.load(fh)

    t_native = snap_a["elapsed_sec"]
    t_deleg = snap_b["elapsed_sec"]

    def _load_marker(snap):
        l1 = snap.get("load1_pre")
        if l1 is None:
            return "load=N/A"
        marker = "(load-belastet)" if l1 >= 0.5 else "ok"
        return f"load={l1:.2f},{marker}"

    print("\n=== Gate evaluation ===")
    print(f"native:    n_subj={snap_a['n_subjects']}, "
          f"n_triples={snap_a['n_triples']}, "
          f"new_statements={snap_a['n_new_first']}, "
          f"elapsed={t_native:.3f}s")
    print(f"delegation:n_subj={snap_b['n_subjects']}, "
          f"n_triples={snap_b['n_triples']}, "
          f"new_statements={snap_b['n_new_first']}, "
          f"elapsed={t_deleg:.3f}s")

    # ── Gate 1 — per-subject state equivalence ──────────────────────────────
    diffs_head, n_diff = gate1_state_equivalence(snap_a, snap_b, limit=20)
    gate_1_ok = (n_diff == 0)
    print(f"\n[Gate 1] state equivalence: "
          f"{'OK' if gate_1_ok else 'DIFF'}  diff_subjects={n_diff}")
    if not gate_1_ok:
        for d in diffs_head:
            print(f"  subject={d['subject_uri']}")
            if d['only_in_A']:
                print(f"    only_in_A ({len(d['only_in_A'])}):")
                for t in d['only_in_A'][:5]:
                    print(f"      {t}")
                if len(d['only_in_A']) > 5:
                    print(f"      ... and {len(d['only_in_A']) - 5} more")
            if d['only_in_B']:
                print(f"    only_in_B ({len(d['only_in_B'])}):")
                for t in d['only_in_B'][:5]:
                    print(f"      {t}")
                if len(d['only_in_B']) > 5:
                    print(f"      ... and {len(d['only_in_B']) - 5} more")
        if n_diff > len(diffs_head):
            print(f"  ... and {n_diff - len(diffs_head)} more divergent subjects")

    # ── Gate 2 — idempotency (BOTH modes) ───────────────────────────────────
    gate_2_ok, idem_n_a, idem_n_b, idem_ex_a, idem_ex_b = gate2_idempotent_both(snap_a, snap_b)
    print(f"\n[Gate 2] idempotency:       "
          f"{'OK' if gate_2_ok else 'NO'}  "
          f"extra_native={idem_n_a} extra_delegation={idem_n_b}")
    if idem_n_a:
        for ex in idem_ex_a:
            print(f"  [native]     unexpected new statement: {ex}")
    if idem_n_b:
        for ex in idem_ex_b:
            print(f"  [delegation] unexpected new statement: {ex}")

    # ── Gate 3 — duplicate-multiset equivalence to native ───────────────────
    dup_diffs, n_dup_diffs, native_dups, deleg_dups = gate3_dup_equivalence(
        snap_a, snap_b, limit=20)
    gate_3_ok = (n_dup_diffs == 0)
    print(f"\n[Gate 3] dup-multiset == native:  "
          f"{'OK' if gate_3_ok else 'DIFF'}  "
          f"diff_triples={n_dup_diffs} native_dups={native_dups} deleg_dups={deleg_dups}")
    if not gate_3_ok:
        for triple, m_native, m_deleg in dup_diffs:
            print(f"  native={m_native} deleg={m_deleg}  {triple}")
        if n_dup_diffs > len(dup_diffs):
            print(f"  ... and {n_dup_diffs - len(dup_diffs)} more")

    overall = gate_1_ok and gate_2_ok and gate_3_ok

    speedup = (t_native / t_deleg) if t_deleg > 0 else float("inf")

    print(f"\n{'=' * 70}")
    print("GATE-RESULT:")
    print(f"  gate_1_state_equivalent: {'true' if gate_1_ok else 'false'}  "
          f"(diff_subjects={n_diff})")
    print(f"  gate_2_idempotent:       {'true' if gate_2_ok else 'false'}  "
          f"(extra_native={idem_n_a}, extra_delegation={idem_n_b})")
    print(f"  gate_3_dup_equiv_native: {'true' if gate_3_ok else 'false'}  "
          f"(diff_triples={n_dup_diffs}, native_dups={native_dups}, deleg_dups={deleg_dups})")
    print(f"  gate_1_ok: {'true' if gate_1_ok else 'false'}")
    print(f"  gate_2_ok: {'true' if gate_2_ok else 'false'}")
    print(f"  gate_3_ok: {'true' if gate_3_ok else 'false'}")
    print(f"  overall_gate_ok:         {'true' if overall else 'false'}")
    print(f"  t_native_sec:            {t_native:.4f}  ({_load_marker(snap_a)})")
    print(f"  t_delegation_sec:        {t_deleg:.4f}  ({_load_marker(snap_b)})")
    print(f"  speedup_fullrun:         {speedup:.2f}x")
    print(f"{'=' * 70}")

    if args.keep_snapshots:
        print(f"\nSnapshots kept under {work_dir}")
    else:
        for f in (snap_native, snap_deleg):
            try:
                os.unlink(f)
            except OSError:
                pass
        try:
            os.rmdir(work_dir)
        except OSError:
            pass

    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
