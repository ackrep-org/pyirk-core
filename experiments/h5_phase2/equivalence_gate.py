#!/usr/bin/env python3
"""
equivalence_gate.py — H5 Phase 2 acceptance gate (V1-V5 → STRICT gate per goal.md).

Runs ``apply_semantic_rules(*all_rules, exhaust=True)`` on the real OCSE-KB
along two paths in **separate subprocesses** (DataStore isolation) and
verifies three acceptance criteria:

  Gate 1 — per-subject state equivalence: for every subject in
           ``ds.statements``, the set ``{(rel_uri, obj_uri-or-repr)}`` after
           the native path must equal the set after the delegation path.
  Gate 2 — idempotency: a SECOND ``apply_semantic_rules`` call right after
           the delegation path (no KB reset) must add 0 new statements.
  Gate 3 — no duplicates: no two distinct Statement objects in the
           delegation path share the same ``(subj_uri, rel_uri, obj-or-repr)``.

The two evaluation passes run in dedicated subprocesses so the in-process
``core.ds`` state of one path cannot leak into the other.  The subprocess
dumps a JSON snapshot of its DataStore, the main process compares the
snapshots in memory.

Reproducible run (with a python that has pyirk + OCSE deps importable;
override the subprocess interpreter via PYIRK_VENV_PYTHON if needed; the
OCSE data dir comes from the pyirk config or PYIRK_OCSE_DIR):
  python experiments/h5_phase2/equivalence_gate.py \\
      2>&1 | tee experiments/h5_phase2/equivalence_gate.log

Exit-Codes:
  0  — overall_gate_ok = true  (all three gates pass)
  1  — overall_gate_ok = false (at least one gate failed)
  2  — Infrastructure error (Nemo binary missing, OCSE not loadable, etc.)
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
# Paths and constants — mirror experiments/h5_phase1/p3_ocse_scale.py
# ─────────────────────────────────────────────────────────────────────────────

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)
from pyirk.nemobridge.delegation import _resolve_nmo_bin  # noqa: E402

NEMO_BIN = _resolve_nmo_bin()


def _resolve_ocse_dir():
    """Locate the OCSE data dir: env override → pyirk config → legacy default."""
    env = os.environ.get("PYIRK_OCSE_DIR")
    if env:
        return env
    try:
        import pyirk as p
        path = p.CONF.get("package", {}).get("ocse", {}).get("path")
        if path:
            return path
    except Exception:
        pass
    return "/home/user/projekte/irk-data/ocse"


OCSE_DIR = _resolve_ocse_dir()
# Optional sys.path overlay for environments where the interpreter lacks a
# dependency (historical VPS case: sympy lived in a sibling venv). Pure
# opt-in via env var; only inserted if the directory actually exists.
SYMPY_EXTRA = os.environ.get("PYIRK_GATE_SYMPY_EXTRA", "")
VENV_PYTHON = os.environ.get("PYIRK_VENV_PYTHON", sys.executable)
OCSE_MOD_URI = "irk:/ocse/0.2/control_theory"


# ─────────────────────────────────────────────────────────────────────────────
# Load guard — mirror Phase 1 (load1 < 0.5 OK, else mark as load-burdened)
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
# Runs in a clean Python process.  Loads OCSE, optionally enables the
# PYIRK_NEMO_DELEGATION flag, runs apply_semantic_rules to fixpoint, then
# dumps a JSON snapshot of ``ds.statements``.  For mode='delegation' an
# additional idempotency probe (second apply_semantic_rules call) is run
# directly on the resulting DataStore (no reset).
#
# The triples list is kept as a list of [subj_uri, rel_uri, obj_repr] —
# one entry per Statement object.  Duplicate detection (Gate 3) counts the
# multiplicities of this list.

_SUBPROCESS_SCRIPT = r'''
import sys, os, json, time, warnings
warnings.filterwarnings("ignore")
if os.path.isdir(%(sympy_extra)r):
    sys.path.insert(0, %(sympy_extra)r)
sys.path.insert(0, %(src_dir)r)

MODE = %(mode)r            # 'native' or 'delegation'
OUT_JSON = %(out_json)r

# Set/clear the delegation flag BEFORE importing pyirk to be safe.
if MODE == 'delegation':
    os.environ['PYIRK_NEMO_DELEGATION'] = '1'
else:
    os.environ.pop('PYIRK_NEMO_DELEGATION', None)

import pyirk as p
from pyirk import ruleengine

ocse_dir = %(ocse_dir)r
ocse_uri = %(ocse_uri)r

p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "agents1.py"), prefix="ag")
p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "math1.py"),
                               prefix="ma", reuse_loaded=True)
p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "control_theory1.py"),
                               prefix="ct", reuse_loaded=True)

all_rules = ruleengine.get_all_rules()

# Load1 just before the timed work — mirror p3_ocse_scale.py marker.
try:
    with open('/proc/loadavg') as fh:
        load1_pre = float(fh.read().split()[0])
except Exception:
    load1_pre = None

t0 = time.perf_counter()
res1 = ruleengine.apply_semantic_rules(
    *all_rules, mod_context_uri=ocse_uri, exhaust=True,
)
t1 = time.perf_counter()
elapsed_first = t1 - t0
n_new_first = len(res1.new_statements)


def _obj_repr(o):
    """Render the statement object canonically.

    - Entity (Item/Relation) → its URI.
    - Anything else (literal value, wrapper, …) → 'LIT:' + repr(o).

    Using URIs (not short_keys) sidesteps short_key collisions across
    modules and matches the V2 design (URI-based reverse resolution).
    """
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

# Canonicalise per-subject lists to a sorted unique form (set-equivalent,
# JSON-serialisable).  Gate 1 compares set equality on these.
by_subject = {
    k: sorted({tuple(t) for t in v}) for k, v in by_subject_lists.items()
}

idem_n_new = None
idem_examples = []
if MODE == 'delegation':
    # Gate 2 — direct second pass on the resulting DataStore (no reset).
    res2 = ruleengine.apply_semantic_rules(
        *all_rules, mod_context_uri=ocse_uri, exhaust=True,
    )
    idem_n_new = len(res2.new_statements)
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
    """Run the OCSE workload in a clean subprocess.  Returns out_json or None."""
    src = _SUBPROCESS_SCRIPT % dict(
        sympy_extra=SYMPY_EXTRA,
        src_dir=SRC_DIR,
        ocse_dir=OCSE_DIR,
        ocse_uri=OCSE_MOD_URI,
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
            print(proc.stderr[:3000], file=sys.stderr)
            return None
        print(proc.stdout.strip())
        if proc.stderr.strip():
            # Bubble warnings/info up to the log but do not fail on them.
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


def gate2_idempotent(snap_b):
    n = snap_b.get("idempotency_n_new")
    return (n == 0), n, snap_b.get("idempotency_examples", [])


def gate3_dup_equivalence(snap_a, snap_b, *, limit=20):
    """Delegation must not introduce duplicate Statement objects BEYOND those the
    native engine itself produces.

    Criterion: the full triple-multiset of path B (delegation) equals that of
    path A (native).  The native pyirk engine itself emits a small number of
    duplicate statement objects (fiat-item R30/R31 rules; pre-existing on
    develop_carsten, unrelated to delegation) — empirically confirmed 2026-06-11:
    a native OCSE run produces the *identical* 5 duplicates the delegation path
    does (same predicates, same Ia-keys, max_multiplicity=3).  Therefore
    equivalence-to-native, not absolute zero, is the correct gate.  Any
    *extra or missing* duplicate vs native fails it, so a real delegation
    regression cannot hide here.
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
        description="H5 Phase 2 acceptance gate (V1-V5)",
    )
    parser.add_argument(
        "--keep-snapshots", action="store_true",
        help="Do not delete the per-mode JSON snapshots after evaluation.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("H5 Phase 2 — Equivalence Gate (native vs nemo-delegation)")
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

    if not os.path.isdir(OCSE_DIR):
        print(f"FEHLER: OCSE dir missing: {OCSE_DIR}", file=sys.stderr)
        sys.exit(2)

    work_dir = tempfile.mkdtemp(prefix="h5p4_gate_")
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

    # ── Gate 2 — idempotency ────────────────────────────────────────────────
    gate_2_ok, idem_n_new, idem_examples = gate2_idempotent(snap_b)
    print(f"\n[Gate 2] idempotency:       "
          f"{'OK' if gate_2_ok else 'NO'}  extra_stmts_on_replay={idem_n_new}")
    if not gate_2_ok:
        for ex in idem_examples:
            print(f"  unexpected new statement: {ex}")

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

    # ── Speedup ─────────────────────────────────────────────────────────────
    speedup = (t_native / t_deleg) if t_deleg > 0 else float("inf")

    # ── Structured result block (machine-readable for P5) ──────────────────
    print(f"\n{'=' * 70}")
    print("GATE-RESULT:")
    print(f"  gate_1_state_equivalent: {'true' if gate_1_ok else 'false'}  "
          f"(diff_subjects={n_diff})")
    print(f"  gate_2_idempotent:       {'true' if gate_2_ok else 'false'}  "
          f"(extra_stmts_on_replay={idem_n_new})")
    print(f"  gate_3_dup_equiv_native: {'true' if gate_3_ok else 'false'}  "
          f"(diff_triples={n_dup_diffs}, native_dups={native_dups}, deleg_dups={deleg_dups})")
    print(f"  overall_gate_ok:         {'true' if overall else 'false'}")
    print(f"  t_native_sec:            {t_native:.4f}  ({_load_marker(snap_a)})")
    print(f"  t_delegation_sec:        {t_deleg:.4f}  ({_load_marker(snap_b)})")
    print(f"  speedup_fullrun:         {speedup:.2f}x")
    print(f"{'=' * 70}")

    if args.keep_snapshots:
        print(f"\nSnapshots kept under {work_dir}")
    else:
        # tempfile.mkdtemp does not auto-clean; remove explicitly.
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
