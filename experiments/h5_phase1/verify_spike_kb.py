"""
verify_spike_kb.py — Full spike-KB verification: R1 (49) and R2 (6).

Runs both the exporter and translator against the spike test-KB and verifies
that Nemo reproduces the baseline results:
  R1 (I64, direct): 49 R83 facts
  R2 (I66, transitive): 6 trans facts for R1001

Exit 0 if both baselines match, else Exit 1 with detail diff.

Usage:
  /home/user/venvs/pyirk-core-venv/bin/python \
      experiments/h5_phase1/verify_spike_kb.py 2>&1 | tee \
      experiments/h5_phase1/verify_spike_kb.log
"""

import csv
import json
import os
import subprocess
import sys
import tempfile

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(HERE, "..", "..")
SPIKE_DIR = os.path.join(REPO_ROOT, "experiments", "h5_spike")
NEMO_BIN = "/home/user/bin/nmo"
BASELINE_R1 = os.path.join(SPIKE_DIR, "baseline_r1.json")
BASELINE_R2 = os.path.join(SPIKE_DIR, "baseline_r2.json")

sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
sys.path.insert(0, SPIKE_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — Check Nemo binary
# ─────────────────────────────────────────────────────────────────────────────

def _check_nemo():
    if not os.path.isfile(NEMO_BIN):
        print(
            f"ERROR: Nemo binary not found at {NEMO_BIN}\n"
            "Please obtain nemo-cli v0.10.0 (Linux amd64 musl) as described in\n"
            f"  {SPIKE_DIR}/README.md\n"
            "and place it at /home/user/bin/nmo.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        proc = subprocess.run([NEMO_BIN, "--version"], capture_output=True, text=True)
        version_str = (proc.stdout + proc.stderr).strip().split("\n")[0]
        print(f"Nemo binary: {NEMO_BIN}")
        print(f"Version:     {version_str}")
    except Exception as e:
        print(f"ERROR: Failed to run {NEMO_BIN}: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_csv_as_set(path: str) -> set:
    if not os.path.exists(path):
        return set()
    result = set()
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if row:
                result.add(tuple(row))
    return result


def _load_json_baseline(path: str) -> set:
    with open(path) as f:
        return set(tuple(row) for row in json.load(f))


def _run_nemo(rules_file: str, import_dir: str, export_dir: str) -> subprocess.CompletedProcess:
    os.makedirs(export_dir, exist_ok=True)
    cmd = [
        NEMO_BIN,
        "--export-dir", export_dir,
        "--import-dir", import_dir,
        "--overwrite-results",
        rules_file,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def _write_rls(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)
    print(f"  RLS written: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main verification
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("H5 Phase 1 — Spike-KB Full Verification (R1 + R2)")
    print("=" * 60)

    # Step 0: Nemo check
    _check_nemo()

    # Step 1: Build test KB
    print("\n=== Step 1: Build test KB ===")
    import pyirk as p
    from create_test_kb import setup_test_module, TEST_MOD_URI
    from pyirk.nemobridge import export_datastore
    from pyirk.nemobridge import classify_rules, generate_transitivity_facts

    setup_test_module()
    print(f"Test KB loaded (module: {TEST_MOD_URI})")

    # Step 2: Export triples.csv
    print("\n=== Step 2: Export EDB to CSV ===")
    tmp_dir = tempfile.mkdtemp(prefix="h5p1_verify_")
    print(f"Working directory: {tmp_dir}")

    audit = export_datastore(p.ds, tmp_dir, per_predicate=True)
    triples_path = audit["paths"]["triples"]
    print(f"  triples.csv: {audit['total_triples']} rows -> {triples_path}")
    print(f"  Predicate counts: {dict(sorted(audit['predicate_counts'].items()))}")

    # Verify R3 count matches R1 baseline count
    with open(BASELINE_R1) as f:
        baseline_r1 = json.load(f)
    expected_r1 = len(baseline_r1)
    r3_count = audit["predicate_counts"].get("R3", 0)
    print(f"  R3 facts: {r3_count}  (R1 baseline expects {expected_r1})")

    # Step 3: Generate .rls files via translator
    print("\n=== Step 3: Generate .rls files ===")

    clfs = classify_rules(p.ds)
    print("  Rule classifications:")
    for c in clfs:
        print(f"    {c.rule_short_key}: {c.category} — {c.reason[:60]}")

    # Phase 2.1: ternary fact-model. The R1 baseline was built from I64 ALONE
    # (no I65 transitive R83 propagation), so we emit two RLS files:
    #  - rules_r1.rls (I64 only)  → reproduces the 49-row R83 baseline
    #  - rules_combined.rls (all)  → reproduces R2 (R1001 closure) as well
    i64_clf = next((c for c in clfs if c.rule_short_key == "I64"), None)
    if i64_clf is None or i64_clf.category != "direct":
        print("ERROR: I64 not classified as 'direct'. Cannot generate R1 rules.", file=sys.stderr)
        p.unload_mod(TEST_MOD_URI, strict=False)
        sys.exit(1)
    r1_rls_content = "\n".join([
        "% R1 verification rules — I64 only (R3 -> R83), ternary fact-model",
        '@import triples :- csv{resource="triples.csv", format=(string,string,string)} .',
        "fact(?s, ?p, ?o) :- triples(?s, ?p, ?o) .",
        "",
        i64_clf.rls_snippet,
        "",
        '@export fact :- csv{resource="output_fact.csv"} .',
    ])
    r1_rls_path = os.path.join(tmp_dir, "rules_r1.rls")
    _write_rls(r1_rls_path, r1_rls_content)

    from pyirk.nemobridge import generate_rls
    combined_rls = generate_rls(p.ds)
    combined_path = os.path.join(tmp_dir, "rules_combined.rls")
    _write_rls(combined_path, combined_rls)

    # Step 4a: Run Nemo with the R1-only RLS (I64 alone)
    print("\n=== Step 4a: Run Nemo — R1 (I64 alone, R3 -> R83) ===")
    r1_out_dir = os.path.join(tmp_dir, "nemo_out_r1")
    r1_proc = _run_nemo(r1_rls_path, tmp_dir, r1_out_dir)
    if r1_proc.returncode != 0:
        print(f"ERROR: Nemo R1 failed (exit {r1_proc.returncode}):", file=sys.stderr)
        print(r1_proc.stderr[:2000], file=sys.stderr)
        p.unload_mod(TEST_MOD_URI, strict=False)
        sys.exit(1)

    # Step 4b: Run Nemo with the combined RLS (for R2 verification)
    print("\n=== Step 4b: Run Nemo — combined (I64/I65 direct + I66 transitive) ===")
    out_dir = os.path.join(tmp_dir, "nemo_out")
    proc = _run_nemo(combined_path, tmp_dir, out_dir)
    if proc.returncode != 0:
        print(f"ERROR: Nemo failed (exit {proc.returncode}):", file=sys.stderr)
        print(proc.stderr[:2000], file=sys.stderr)
        p.unload_mod(TEST_MOD_URI, strict=False)
        sys.exit(1)

    # Output cells are quoted strings: csv.reader returns each cell as
    # "<uri>" (with literal surrounding double quotes). Strip them.
    def _strip_q(s: str) -> str:
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s

    def _read_fact_csv(path):
        rows = set()
        if not os.path.exists(path):
            return rows
        with open(path, newline="") as fh:
            for row in csv.reader(fh):
                if len(row) >= 3:
                    rows.add(tuple(_strip_q(c) for c in row[:3]))
        return rows

    nemo_r1_rows = _read_fact_csv(os.path.join(r1_out_dir, "output_fact.csv"))
    nemo_fact_rows = _read_fact_csv(os.path.join(out_dir, "output_fact.csv"))
    print(f"  R1 output_fact.csv rows: {len(nemo_r1_rows)}")
    print(f"  combined output_fact.csv rows: {len(nemo_fact_rows)}")

    # R1 verification — filter R1-only output for predicate == R83.uri
    r83_uri = p.R83.uri
    r3_uri = p.R3.uri
    nemo_r83_pairs = {(s, o) for (s, pred, o) in nemo_r1_rows if pred == r83_uri}
    # Map back to short_keys for comparison with the baseline (which uses short_keys)
    def _sk(uri: str) -> str:
        try:
            return p.ds.get_entity_by_uri(uri).short_key
        except Exception:
            return uri.split("#", 1)[-1]
    nemo_r83_pairs_sk = {(_sk(s), _sk(o)) for s, o in nemo_r83_pairs}
    baseline_r1_pairs = {(row[0], row[2]) for row in baseline_r1}
    ok_r1 = (nemo_r83_pairs_sk == baseline_r1_pairs)

    if ok_r1:
        print(f"  R1: OK — {len(nemo_r83_pairs_sk)}/{expected_r1} R83 facts match baseline")
    else:
        only_baseline = baseline_r1_pairs - nemo_r83_pairs_sk
        only_nemo = nemo_r83_pairs_sk - baseline_r1_pairs
        print(f"  R1: FAIL — expected {expected_r1}, got {len(nemo_r83_pairs_sk)}", file=sys.stderr)
        if only_baseline:
            print(f"    In baseline but not Nemo ({len(only_baseline)}):", file=sys.stderr)
            for t in sorted(only_baseline)[:5]:
                print(f"      {t}", file=sys.stderr)
        if only_nemo:
            print(f"    In Nemo but not baseline ({len(only_nemo)}):", file=sys.stderr)
            for t in sorted(only_nemo)[:5]:
                print(f"      {t}", file=sys.stderr)

    # Step 5: R2 verification — filter on R1001 URI
    print("\n=== Step 5: R2 (I66, transitive closure over R1001) ===")
    r1001 = p.ds.get_entity_by_uri("irk:/h5_spike/test_kb#R1001")
    r1001_uri = r1001.uri
    nemo_r2_r1001 = {
        (_sk(s), "R1001", _sk(o))
        for (s, pred, o) in nemo_fact_rows
        if pred == r1001_uri
    }
    baseline_r2 = _load_json_baseline(BASELINE_R2)
    expected_r2 = len(baseline_r2)
    # baseline includes the input base chain too (Nemo's fact also includes them
    # since fact is seeded from triples); compare directly.
    ok_r2 = (nemo_r2_r1001 == baseline_r2)

    if ok_r2:
        print(f"  R2: OK — {len(nemo_r2_r1001)}/{expected_r2} R1001 trans facts match baseline")
    else:
        only_baseline = baseline_r2 - nemo_r2_r1001
        only_nemo = nemo_r2_r1001 - baseline_r2
        print(f"  R2: FAIL — expected {expected_r2} R1001 facts, got {len(nemo_r2_r1001)}", file=sys.stderr)
        if only_baseline:
            print(f"    In baseline but not Nemo ({len(only_baseline)}):", file=sys.stderr)
            for t in sorted(only_baseline)[:5]:
                print(f"      {t}", file=sys.stderr)
        if only_nemo:
            print(f"    In Nemo but not baseline ({len(only_nemo)}):", file=sys.stderr)
            for t in sorted(only_nemo)[:5]:
                print(f"      {t}", file=sys.stderr)

    # Summary
    print("\n=== VERIFICATION SUMMARY ===")
    print(f"  R1 (I64, R3→R83): {'OK' if ok_r1 else 'FAIL'} ({len(nemo_r83_pairs_sk)}/{expected_r1})")
    print(f"  R2 (I66, trans):  {'OK' if ok_r2 else 'FAIL'} ({len(nemo_r2_r1001)}/{expected_r2})")
    print(f"  Temp dir: {tmp_dir}")
    print(f"  RLS file: {combined_path}")

    p.unload_mod(TEST_MOD_URI, strict=False)

    if ok_r1 and ok_r2:
        print("\nVERIFICATION: PASS")
        sys.exit(0)
    else:
        print("\nVERIFICATION: FAIL", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
