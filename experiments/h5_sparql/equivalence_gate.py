#!/usr/bin/env python3
"""
equivalence_gate.py — H5 SPARQL acceptance gate for the Zebra rule set.

Runs a curated set of zebra rules — see ``ZEBRA_RULE_KEYS`` below — through
``apply_semantic_rules(*selected, exhaust=True)`` on the **full** Zebra KB
(``zebra_base_data`` + ``zebra_puzzle_rules`` + ``zebra02`` puzzle instance)
along two paths in **separate subprocesses** (DataStore isolation) and
verifies three acceptance criteria modelled after the recalibrated
Phase 2.1 gates:

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

In addition, per-rule subprocesses apply ONE rule each on the fresh KB and
report the new_statements count plus the new-statement multiset.  The
per-rule table contrasts native_count and delegated_count for every rule in
``ZEBRA_RULE_KEYS``.  This is informational; the three top-level gates
remain the acceptance criterion.

KB choice: zb + zr + zebra02 is "Voll-KB (Zebra)" — full zebra base data,
puzzle rules, and a concrete puzzle instance so the BGP-premise rules
actually have R50/R3606/R57 facts to bind against.  The extension gate's
zebra-only KB (zb+zr) would let the new SPARQL rules fire 0 times and the
per-rule table would be trivially zero.

Curated exclusions (NOT in ZEBRA_RULE_KEYS) — see translator.py's
``_SPARQL_PYTHON_ONLY_RULE_KEYS`` and ``experiments/h5_sparql/recon.md``:

  * I725 — native crashes with AssertionError on the zebra-only KB
    because its SPARQL premise binds object positions that can resolve to
    literals (``ruleengine.py::_process_result_map``).  Translator forces
    ``python_only`` via the curated key set.
  * I803 — BGP premise binds R39-statements that pyirk's ``new_tuple``
    qualifies with ``has_index``.  The Nemo exporter routes qualified
    statements to ``stmts.csv``/``quals_*.csv`` instead of ``triples.csv``;
    the EDB seed ``fact(?s,?p,?o) :- triples(?s,?p,?o)`` never produces the
    fact, so delegated count is 0 while native is ~88.  Fix would require
    cross-cutting EDB-seed extension — out-of-scope for Stage 4.
  * I741 — Stage-5 Honest-Stop.  Filter+Minus; translator negation not
    implemented.  Prerequisite proof (Nemo NaF == native MINUS) is its own
    increment; budget reserve insufficient.

Reproducible runs (with a python that has pyirk + test deps importable;
override the subprocess interpreter via PYIRK_VENV_PYTHON if needed):
  python experiments/h5_sparql/equivalence_gate.py \\
      > experiments/h5_sparql/equivalence_gate.log 2>&1

  # The PYIRK_NEMO_DELEGATION env var does not need to be set: the gate
  # always runs the *native* subprocess with the flag cleared and the
  # *delegation* subprocess with the flag set, regardless of the env.

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
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)
from pyirk.nemobridge.delegation import _resolve_nmo_bin  # noqa: E402

NEMO_BIN = _resolve_nmo_bin()
# Optional sys.path overlay for environments where the interpreter lacks a
# dependency (historical VPS case: sympy lived in a sibling venv). Pure
# opt-in via env var; only inserted if the directory actually exists.
SYMPY_EXTRA = os.environ.get("PYIRK_GATE_SYMPY_EXTRA", "")
VENV_PYTHON = os.environ.get("PYIRK_VENV_PYTHON", sys.executable)
ZEBRA_BASE_DATA_PATH = os.path.join(
    REPO_ROOT, "tests", "test_data", "zebra_base_data.py",
)
ZEBRA_RULES_PATH = os.path.join(
    REPO_ROOT, "tests", "test_data", "zebra_puzzle_rules.py",
)
ZEBRA02_PATH = os.path.join(
    REPO_ROOT, "tests", "test_data", "zebra02.py",
)
ZEBRA_RULES_URI = "irk:/ocse/0.2/zebra_puzzle_rules"

# Curated set of zebra rules applied by the gate. Same five literal-premise
# rules as the H5 Extension gate (I702/I705/I790/I800/I820) plus the five
# SPARQL-BGP rules that Stage 1+2+4 of the H5 SPARQL increment delegate to
# Nemo (I710/I730/I740/I792/I798). The Zebra KB used here (zb + zr + zebra02)
# is the same one the per-rule fixture tests in ``tests/test_h5_sparql_*``
# exercise, so the BGP-premise rules can bind against R50/R3606/R57 facts.
ZEBRA_RULE_KEYS = (
    "I702", "I705", "I790", "I800", "I820",
    "I710", "I730", "I740", "I792", "I798",
)

# Per-rule prerequisite chain for the per-rule isolation table. Mirrors the
# fixture chain in tests/test_h5_sparql_premises.py so the BGP-premise rules
# bind against R50/R3606/R57 facts that need I702 (reverse-statements
# callback) and I705 (different-from) to populate first. The new SPARQL
# rules without prereqs fire 0 times even on zb+zr+zebra02 — applying the
# prereqs makes the table truly informative for the per-rule comparison.
PERRULE_PREREQS = {
    "I702": (),
    "I705": (),
    "I790": (),
    "I800": (),
    "I820": (),
    "I710": ("I702", "I705"),
    "I730": ("I702", "I705"),
    "I740": ("I702", "I705", "I730", "I792"),
    "I792": ("I702", "I705", "I730"),
    "I798": ("I702", "I705"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Load guard — mirror Phase 2 / extension gate
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
# Subprocess script template — aggregate gate (all rules together, fixpoint)
# ─────────────────────────────────────────────────────────────────────────────

_AGG_SUBPROCESS_SCRIPT = r'''
import sys, os, json, time, warnings
warnings.filterwarnings("ignore")
if os.path.isdir(%(sympy_extra)r):
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
z2 = p.irkloader.load_mod_from_path(%(zebra02)r, prefix='z2', reuse_loaded=True)

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


# ─────────────────────────────────────────────────────────────────────────────
# Subprocess script template — per-rule (one rule on fresh KB)
# ─────────────────────────────────────────────────────────────────────────────
#
# Applies a SINGLE rule (no exhaust loop) on the freshly-loaded KB.  Captures
# the multiset of new statements the rule produced.  Used to fill the
# per-rule table in the gate log.  Note: this measures the rule's
# contribution in *isolation* (no cascading from other rules), which is the
# fairest like-for-like comparison between native and delegated paths.

_PERRULE_SUBPROCESS_SCRIPT = r'''
import sys, os, json, time, warnings
warnings.filterwarnings("ignore")
if os.path.isdir(%(sympy_extra)r):
    sys.path.insert(0, %(sympy_extra)r)
sys.path.insert(0, %(src_dir)r)

MODE = %(mode)r            # 'native' or 'delegation'
OUT_JSON = %(out_json)r
RULE_KEY = %(rule_key)r
PREREQ_KEYS = %(prereq_keys)r

if MODE == 'delegation':
    os.environ['PYIRK_NEMO_DELEGATION'] = '1'
else:
    os.environ.pop('PYIRK_NEMO_DELEGATION', None)

import pyirk as p
from pyirk import ruleengine

zb = p.irkloader.load_mod_from_path(%(zebra_base_data)r, prefix='zb')
zr = p.irkloader.load_mod_from_path(%(zebra_rules)r, prefix='zr', reuse_loaded=True)
z2 = p.irkloader.load_mod_from_path(%(zebra02)r, prefix='z2', reuse_loaded=True)

zebra_rules_uri = %(zebra_rules_uri)r

# Apply prerequisite rules under the SAME flag setting in both modes so
# the starting state for the measured rule matches between native and
# delegated subprocesses.
for prereq_key in PREREQ_KEYS:
    ruleengine.apply_semantic_rules(
        getattr(zr, prereq_key), mod_context_uri=zebra_rules_uri,
    )

rule = getattr(zr, RULE_KEY)

t0 = time.perf_counter()
res = ruleengine.apply_semantic_rules(
    rule, mod_context_uri=zebra_rules_uri,
)
elapsed = time.perf_counter() - t0


def _obj_repr(o):
    uri = getattr(o, 'uri', None)
    if uri is not None:
        return uri
    return 'LIT:' + repr(o)


triples = []
for stm in res.new_statements:
    try:
        s_uri = stm.subject.uri
    except Exception:
        s_uri = repr(stm.subject)
    try:
        r_uri = stm.predicate.uri
    except Exception:
        r_uri = repr(stm.predicate)
    triples.append([s_uri, r_uri, _obj_repr(stm.object)])

with open(OUT_JSON, 'w', encoding='utf-8') as fh:
    json.dump({
        'mode': MODE,
        'rule_key': RULE_KEY,
        'elapsed_sec': elapsed,
        'n_new': len(triples),
        'triples': triples,
    }, fh)

print(f"per-rule {MODE} {RULE_KEY}: elapsed={elapsed:.3f}s n_new={len(triples)}")
'''


def _run_subprocess(script_src, *, mode, label, timeout=600):
    """Run *script_src* in a clean subprocess. Returns True on success."""
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, encoding="utf-8",
    ) as fh:
        fh.write(script_src)
        script_path = fh.name
    try:
        proc = subprocess.run(
            [VENV_PYTHON, script_path],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            print(
                f"FEHLER ({label}-subprocess exit {proc.returncode}):",
                file=sys.stderr,
            )
            print("---- stdout ----", file=sys.stderr)
            print(proc.stdout[:20000], file=sys.stderr)
            print("---- stderr ----", file=sys.stderr)
            print(proc.stderr[:20000], file=sys.stderr)
            return False
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.stderr.strip():
            print(f"[{label} stderr] {proc.stderr.strip()[:600]}", file=sys.stderr)
        return True
    finally:
        os.unlink(script_path)


def run_aggregate_subprocess(mode, out_json, timeout=1200):
    """Run the full ZEBRA_RULE_KEYS workload in a clean subprocess."""
    src = _AGG_SUBPROCESS_SCRIPT % dict(
        sympy_extra=SYMPY_EXTRA,
        src_dir=SRC_DIR,
        zebra_base_data=ZEBRA_BASE_DATA_PATH,
        zebra_rules=ZEBRA_RULES_PATH,
        zebra02=ZEBRA02_PATH,
        zebra_rules_uri=ZEBRA_RULES_URI,
        rule_keys=ZEBRA_RULE_KEYS,
        mode=mode,
        out_json=out_json,
    )
    return _run_subprocess(src, mode=mode, label=f"aggregate-{mode}", timeout=timeout)


def run_perrule_subprocess(mode, rule_key, out_json, prereq_keys, timeout=300):
    """Run a single rule in isolation (after prereqs) on a clean subprocess."""
    src = _PERRULE_SUBPROCESS_SCRIPT % dict(
        sympy_extra=SYMPY_EXTRA,
        src_dir=SRC_DIR,
        zebra_base_data=ZEBRA_BASE_DATA_PATH,
        zebra_rules=ZEBRA_RULES_PATH,
        zebra02=ZEBRA02_PATH,
        zebra_rules_uri=ZEBRA_RULES_URI,
        rule_key=rule_key,
        prereq_keys=tuple(prereq_keys),
        mode=mode,
        out_json=out_json,
    )
    return _run_subprocess(src, mode=mode, label=f"{rule_key}-{mode}", timeout=timeout)


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
        description="H5 SPARQL acceptance gate (Zebra)",
    )
    parser.add_argument(
        "--keep-snapshots", action="store_true",
        help="Do not delete the per-mode JSON snapshots after evaluation.",
    )
    parser.add_argument(
        "--no-per-rule", action="store_true",
        help="Skip the per-rule subprocess pairs (faster smoke run).",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("H5 SPARQL — Zebra Equivalence Gate (native vs nemo-delegation)")
    print(f"  Voll-KB: zb + zr + zebra02 ; rules: {list(ZEBRA_RULE_KEYS)}")
    print("=" * 70)

    # Pre-flight ---------------------------------------------------------------
    print("\n=== Pre-flight ===")
    lg_pre = load_guard()
    print(f"uptime load (1-min): {lg_pre['load_str']}")
    if lg_pre["load_burdened"]:
        for w in lg_pre["warnings"]:
            print(f"  WARNUNG: {w}")
        print("  → measurements proceed, but get a '(load-belastet)' marker.")

    if NEMO_BIN is None or not os.path.isfile(NEMO_BIN):
        print(
            "FEHLER: no nmo binary found (PYIRK_NEMO_BIN, PATH, ~/bin/nmo)",
            file=sys.stderr,
        )
        sys.exit(2)
    proc = subprocess.run([NEMO_BIN, "--version"], capture_output=True, text=True)
    nemo_version = (proc.stdout + proc.stderr).strip().split("\n")[0]
    print(f"Nemo: {nemo_version}")

    for path in (ZEBRA_BASE_DATA_PATH, ZEBRA_RULES_PATH, ZEBRA02_PATH):
        if not os.path.isfile(path):
            print(f"FEHLER: Zebra source missing: {path}", file=sys.stderr)
            sys.exit(2)

    work_dir = tempfile.mkdtemp(prefix="h5sparql_gate_")
    snap_native = os.path.join(work_dir, "snap_native.json")
    snap_deleg = os.path.join(work_dir, "snap_delegation.json")

    # Path A — native ----------------------------------------------------------
    print("\n=== Pfad A — native (subprocess) ===")
    t0 = time.perf_counter()
    if not run_aggregate_subprocess("native", snap_native):
        print("FEHLER: native subprocess failed → exit 2", file=sys.stderr)
        sys.exit(2)
    wall_a = time.perf_counter() - t0
    print(f"native subprocess wall: {wall_a:.3f}s")

    # Path B — delegation ------------------------------------------------------
    print("\n=== Pfad B — delegation (subprocess) ===")
    t0 = time.perf_counter()
    if not run_aggregate_subprocess("delegation", snap_deleg):
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

    # ── Per-rule isolation table ────────────────────────────────────────────
    perrule_rows = []
    perrule_ok = True
    if not args.no_per_rule:
        print("\n=== Per-rule isolation (single rule on fresh KB after prereqs) ===")
        for rule_key in ZEBRA_RULE_KEYS:
            pr_native_json = os.path.join(work_dir, f"perrule_{rule_key}_native.json")
            pr_deleg_json = os.path.join(work_dir, f"perrule_{rule_key}_delegation.json")
            prereqs = PERRULE_PREREQS.get(rule_key, ())
            ok_n = run_perrule_subprocess("native", rule_key, pr_native_json, prereqs)
            ok_d = run_perrule_subprocess("delegation", rule_key, pr_deleg_json, prereqs)
            if not (ok_n and ok_d):
                perrule_rows.append((rule_key, None, None, False, "subprocess failed"))
                perrule_ok = False
                continue
            with open(pr_native_json, "r", encoding="utf-8") as fh:
                pn = json.load(fh)
            with open(pr_deleg_json, "r", encoding="utf-8") as fh:
                pd = json.load(fh)
            c_n = Counter(tuple(t) for t in pn["triples"])
            c_d = Counter(tuple(t) for t in pd["triples"])
            multiset_eq = (c_n == c_d)
            perrule_rows.append((rule_key, pn["n_new"], pd["n_new"], multiset_eq, ""))

        # pretty-print table
        print()
        print(f"  {'rule':<6} | {'native_count':>12} | {'delegated_count':>15} | {'multiset_gleich':>15}")
        print(f"  {'-'*6}-+-{'-'*12}-+-{'-'*15}-+-{'-'*15}")
        for (k, nn, nd, eq, err) in perrule_rows:
            if err:
                print(f"  {k:<6} | {'?':>12} | {'?':>15} | {'ERR: ' + err}")
            else:
                print(f"  {k:<6} | {nn:>12} | {nd:>15} | {'true' if eq else 'false':>15}")

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
    if not args.no_per_rule:
        per_rule_summary = ", ".join(
            f"{k}:n={nn}/d={nd}{'=' if eq else '≠'}" for (k, nn, nd, eq, _) in perrule_rows
        )
        print(f"  per_rule_isolation:      {per_rule_summary}")
    print(f"{'=' * 70}")

    if args.keep_snapshots:
        print(f"\nSnapshots kept under {work_dir}")
    else:
        for f in os.listdir(work_dir):
            try:
                os.unlink(os.path.join(work_dir, f))
            except OSError:
                pass
        try:
            os.rmdir(work_dir)
        except OSError:
            pass

    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
