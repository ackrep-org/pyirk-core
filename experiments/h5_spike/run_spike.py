"""
run_spike.py - Orchestrierung: Exporter + Nemo-Lauf + Korrektheitsabgleich + Timing

Standalone ausfuehrbar:
  cd /home/user/projekte/pyirk-core
  python experiments/h5_spike/run_spike.py
"""

import sys
import os
import json
import csv
import subprocess
import time
import timeit
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))
NEMO_BIN = "/tmp/nmo"
RULES_R1 = os.path.join(SPIKE_DIR, "rules_r1.rls")
RULES_R2 = os.path.join(SPIKE_DIR, "rules_r2.rls")
R1_CSV = os.path.join(SPIKE_DIR, "facts_for_r1.csv")
R2_CSV = os.path.join(SPIKE_DIR, "facts_for_r2.csv")
BASELINE_R1_PATH = os.path.join(SPIKE_DIR, "baseline_r1.json")
BASELINE_R2_PATH = os.path.join(SPIKE_DIR, "baseline_r2.json")
NEMO_OUT_R1 = "/tmp/nemo_out_r1"
NEMO_OUT_R2 = "/tmp/nemo_out_r2"

TEST_MOD_URI = "irk:/h5_spike/test_kb"

import pyirk as p
from exporter import export_r3_facts, export_transitive_triple_facts
from create_test_kb import (
    setup_test_module,
    get_derived_baseline_for_relation,
    save_baselines,
)


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def load_baseline(path) -> set:
    """Laedt eine Baseline als Set von Tupeln."""
    with open(path) as f:
        return set(tuple(row) for row in json.load(f))


def run_nemo(rules_file: str, export_dir: str, import_dir: str) -> subprocess.CompletedProcess:
    """Fuehrt Nemo aus und gibt das Ergebnis-Objekt zurueck."""
    os.makedirs(export_dir, exist_ok=True)
    cmd = [
        NEMO_BIN,
        "--export-dir", export_dir,
        "--import-dir", import_dir,
        "--overwrite-results",
        rules_file,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=SPIKE_DIR)


def load_csv_as_set(path: str) -> set:
    """Laedt CSV-Datei als Set von Tupeln."""
    if not os.path.exists(path):
        return set()
    result = set()
    with open(path, newline="") as f:
        for row in csv.reader(f):
            result.add(tuple(row))
    return result


def teardown_pyirk_test_module():
    """Entlaedt das Test-Modul und bereinigt den DataStore."""
    p.unload_mod(TEST_MOD_URI, strict=False)


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 1: Test-KB aufbauen, Fakten exportieren
# ─────────────────────────────────────────────────────────────────────────────

def build_facts_and_baseline():
    """Erstellt Testdaten, exportiert CSVs, erstellt Baselines."""
    print("\n=== Schritt 1: Test-KB aufbauen und Fakten exportieren ===")

    entities = setup_test_module()

    # CSV-Fakten exportieren
    n_r1 = export_r3_facts(p.ds, R1_CSV)
    print(f"R3-Fakten exportiert: {n_r1} Zeilen -> {R1_CSV}")

    RT = entities["R1001"]
    n_r2 = export_transitive_triple_facts(p.ds, RT, R2_CSV)
    print(f"RT-Fakten exportiert: {n_r2} Zeilen -> {R2_CSV}")

    # Baseline fuer R1 (I64 only)
    res_i64 = p.ruleengine.apply_semantic_rule(p.I64, mod_context_uri=TEST_MOD_URI)
    print(f"pyirk I64: {len(res_i64.new_statements)} neue Statements")
    # R83-Baseline aus exportierten R3-Fakten (konsistent mit Exporter-Filter fuer Scope-Items)
    r83_baseline = set()
    with open(R1_CSV, newline="") as f_r1:
        for row_r1 in csv.reader(f_r1):
            if len(row_r1) >= 2:
                r83_baseline.add((row_r1[0], "R83", row_r1[1]))
    print(f"R83-Baseline (aus exportierten R3): {len(r83_baseline)} Statements")

    # Baseline fuer R2 (I66 exhaustiv)
    res_i66 = p.ruleengine.apply_semantic_rules(p.I66, mod_context_uri=TEST_MOD_URI, exhaust=True)
    print(f"pyirk I66 exhaustiv: {len(res_i66.new_statements)} neue Statements")
    rt_baseline = get_derived_baseline_for_relation(RT)
    print(f"RT-Baseline: {len(rt_baseline)} Statements gesamt")

    save_baselines(r83_baseline, rt_baseline)
    teardown_pyirk_test_module()

    return r83_baseline, rt_baseline


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 2: Nemo-Lauf R1
# ─────────────────────────────────────────────────────────────────────────────

def run_nemo_r1() -> set:
    """Fuehrt Nemo fuer R1 (I64) aus und gibt das Ergebnis als Set zurueck."""
    result = run_nemo(RULES_R1, NEMO_OUT_R1, SPIKE_DIR)
    if result.returncode != 0:
        print(f"FEHLER bei Nemo R1:\n{result.stderr}")
        return set()
    output_csv = os.path.join(NEMO_OUT_R1, "output_r1.csv")
    raw = load_csv_as_set(output_csv)
    # Normalisierung: Nemo gibt (subj, obj) ohne Pred-Spalte aus; wir haengen R83 an
    return set((s, "R83", o) for s, o in raw)


def run_nemo_r2() -> set:
    """Fuehrt Nemo fuer R2 (I66) aus und gibt alle (basis + abgeleitete) Tripel als Set zurueck."""
    result = run_nemo(RULES_R2, NEMO_OUT_R2, SPIKE_DIR)
    if result.returncode != 0:
        print(f"FEHLER bei Nemo R2:\n{result.stderr}")
        return set(), set()
    new_csv = os.path.join(NEMO_OUT_R2, "output_r2_new.csv")
    all_csv = os.path.join(NEMO_OUT_R2, "output_r2_all.csv")
    nemo_new = load_csv_as_set(new_csv)
    nemo_all = load_csv_as_set(all_csv)
    return nemo_new, nemo_all


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 3: Korrektheitsabgleich
# ─────────────────────────────────────────────────────────────────────────────

def correctness_check(pyirk_set: set, nemo_set: set, label: str) -> bool:
    """Vergleicht zwei Sets und gibt True zurueck wenn gleich."""
    diff = pyirk_set.symmetric_difference(nemo_set)
    if not diff:
        print(f"  {label}: OK (beide Sets identisch, {len(pyirk_set)} Statements)")
        return True
    else:
        only_pyirk = pyirk_set - nemo_set
        only_nemo = nemo_set - pyirk_set
        print(f"  {label}: FEHLER - symmetrische Differenz: {len(diff)} Statements")
        if only_pyirk:
            print(f"    Nur in pyirk ({len(only_pyirk)}):")
            for t in sorted(only_pyirk)[:10]:
                print(f"      {t}")
        if only_nemo:
            print(f"    Nur in Nemo ({len(only_nemo)}):")
            for t in sorted(only_nemo)[:10]:
                print(f"      {t}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 4: Timing
# ─────────────────────────────────────────────────────────────────────────────

def time_pyirk_i64() -> float:
    """Misst Zeit fuer einen pyirk I64-Lauf (frischer DataStore-Zustand)."""
    setup_test_module()

    t0 = time.perf_counter()
    p.ruleengine.apply_semantic_rule(p.I64, mod_context_uri=TEST_MOD_URI)
    elapsed = time.perf_counter() - t0

    teardown_pyirk_test_module()
    return elapsed


def time_pyirk_i66() -> float:
    """Misst Zeit fuer einen pyirk I66-Lauf (frischer DataStore-Zustand)."""
    setup_test_module()

    t0 = time.perf_counter()
    p.ruleengine.apply_semantic_rules(p.I66, mod_context_uri=TEST_MOD_URI, exhaust=True)
    elapsed = time.perf_counter() - t0

    teardown_pyirk_test_module()
    return elapsed


def time_nemo_r1() -> float:
    """Misst Zeit fuer den vollstaendigen Nemo R1-Pipeline-Lauf (Export + Nemo + Import)."""
    entities = setup_test_module()

    t0 = time.perf_counter()

    # Export
    tmp_r1_csv = "/tmp/nemo_timing_r1.csv"
    export_r3_facts(p.ds, tmp_r1_csv)

    # Nemo-Lauf
    tmp_out = "/tmp/nemo_timing_r1_out"
    shutil.rmtree(tmp_out, ignore_errors=True)
    os.makedirs(tmp_out, exist_ok=True)

    # Temporaere rules-Datei mit angepasstem Pfad
    tmp_rules = "/tmp/nemo_timing_r1.rls"
    with open(tmp_rules, "w") as f:
        f.write('@import is_subclass_of :- csv{resource="nemo_timing_r1.csv"} .\n')
        f.write("is_generalized_subclass(?i2, ?i1) :- is_subclass_of(?i2, ?i1) .\n")
        f.write('@export is_generalized_subclass :- csv{resource="output_r1.csv"} .\n')

    subprocess.run(
        [NEMO_BIN, "--export-dir", tmp_out, "--import-dir", "/tmp", "--overwrite-results", tmp_rules],
        capture_output=True, text=True
    )

    # Import (Ergebnis einlesen)
    load_csv_as_set(os.path.join(tmp_out, "output_r1.csv"))

    elapsed = time.perf_counter() - t0

    teardown_pyirk_test_module()
    return elapsed


def time_nemo_r2() -> float:
    """Misst Zeit fuer den vollstaendigen Nemo R2-Pipeline-Lauf."""
    entities = setup_test_module()
    RT = entities["R1001"]

    t0 = time.perf_counter()

    # Export
    tmp_r2_csv = "/tmp/nemo_timing_r2.csv"
    export_transitive_triple_facts(p.ds, RT, tmp_r2_csv)

    # Nemo-Lauf
    tmp_out = "/tmp/nemo_timing_r2_out"
    shutil.rmtree(tmp_out, ignore_errors=True)
    os.makedirs(tmp_out, exist_ok=True)

    tmp_rules = "/tmp/nemo_timing_r2.rls"
    with open(tmp_rules, "w") as f:
        f.write('@import base_triple :- csv{resource="nemo_timing_r2.csv"} .\n')
        f.write('is_transitive(R1001) .\n')
        f.write('trans(?s, ?p, ?o) :- base_triple(?s, ?p, ?o) .\n')
        f.write('trans(?i1, ?r, ?i3) :- is_transitive(?r), trans(?i1, ?r, ?i2), trans(?i2, ?r, ?i3) .\n')
        f.write('@export trans :- csv{resource="output_r2.csv"} .\n')

    subprocess.run(
        [NEMO_BIN, "--export-dir", tmp_out, "--import-dir", "/tmp", "--overwrite-results", tmp_rules],
        capture_output=True, text=True
    )

    # Import
    load_csv_as_set(os.path.join(tmp_out, "output_r2.csv"))

    elapsed = time.perf_counter() - t0

    teardown_pyirk_test_module()
    return elapsed


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("H5-Spike: Nemo-Delegierbarkeitstest")
    print("=" * 60)

    # Schritt 1: Test-KB aufbauen + Fakten exportieren
    r83_baseline, rt_baseline = build_facts_and_baseline()

    # Schritt 2: Nemo-Laeufe
    print("\n=== Schritt 2: Nemo-Laeufe ===")
    print("Nemo R1 (I64)...")
    nemo_r1_set = run_nemo_r1()
    print(f"Nemo R1 lieferte {len(nemo_r1_set)} Statements")

    print("Nemo R2 (I66)...")
    nemo_r2_new, nemo_r2_all = run_nemo_r2()
    print(f"Nemo R2 lieferte {len(nemo_r2_new)} Statements (vollstaendige transitive Huelle)")

    # Schritt 3: Korrektheitsabgleich
    print("\n=== KORREKTHEITSABGLEICH ===")

    ok_r1 = correctness_check(r83_baseline, nemo_r1_set, "R1 (I64)")
    print()

    # Fuer R2: nemo_r2_new enthaelt jetzt die vollstaendige transitive Huelle (Basis + Abgeleitet)
    ok_r2 = correctness_check(rt_baseline, nemo_r2_new, "R2 (I66)")

    print()
    print("=== KORREKTHEITSERGEBNIS ZUSAMMENFASSUNG ===")
    print(f"  R1 (I64): {'OK' if ok_r1 else 'FEHLER'}")
    print(f"  R2 (I66): {'OK' if ok_r2 else 'FEHLER'} (bedingt delegierbar - statische Rel.-Liste)")

    # Schritt 4: Timing
    print("\n=== Schritt 4: Timing (best-of-3) ===")
    print("Messe pyirk I64 (3x)...")
    times_pyirk_i64 = [time_pyirk_i64() for _ in range(3)]

    print("Messe Nemo R1-Pipeline (3x)...")
    times_nemo_r1 = [time_nemo_r1() for _ in range(3)]

    print("Messe pyirk I66 exhaustiv (3x)...")
    times_pyirk_i66 = [time_pyirk_i66() for _ in range(3)]

    print("Messe Nemo R2-Pipeline (3x)...")
    times_nemo_r2 = [time_nemo_r2() for _ in range(3)]

    print("\n=== TIMING (best-of-3) ===")
    header = f"{'Variante':<25} {'Min (s)':>8} {'Lauf 1':>8} {'Lauf 2':>8} {'Lauf 3':>8}"
    print(header)
    print("-" * len(header))

    def fmt_row(name, times):
        return (f"{name:<25} {min(times):>8.4f} {times[0]:>8.4f} {times[1]:>8.4f} {times[2]:>8.4f}")

    rows = [
        fmt_row("pyirk I64", times_pyirk_i64),
        fmt_row("Nemo R1", times_nemo_r1),
        fmt_row("pyirk I66 (exhaust)", times_pyirk_i66),
        fmt_row("Nemo R2", times_nemo_r2),
    ]
    for row in rows:
        print(row)

    return {
        "ok_r1": ok_r1,
        "ok_r2": ok_r2,
        "times": {
            "pyirk_i64": times_pyirk_i64,
            "nemo_r1": times_nemo_r1,
            "pyirk_i66": times_pyirk_i66,
            "nemo_r2": times_nemo_r2,
        },
        "counts": {
            "r83_baseline": len(r83_baseline),
            "nemo_r1": len(nemo_r1_set),
            "rt_baseline": len(rt_baseline),
            "nemo_r2_new": len(nemo_r2_new),
            "nemo_r2_all": len(nemo_r2_all),
        },
    }


if __name__ == "__main__":
    results = main()
    # Ergebnis als JSON speichern
    results_json = os.path.join(SPIKE_DIR, "timing_results.json")
    with open(results_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nErgebnisse gespeichert: {results_json}")
    print("\nrun_spike.py: fertig.")
