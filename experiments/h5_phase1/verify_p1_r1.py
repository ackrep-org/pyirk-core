"""
verify_p1_r1.py — Teilverifikation R1 (49/49)

Exportiert R3-Fakten aus der Spike-Test-KB via den neuen nemobridge-Exporter
und vergleicht die Zeilenzahl mit der Baseline (baseline_r1.json, 49 Eintraege).

Exit 0 bei Erfolg, Exit 1 bei Fehler.
"""

import json
import os
import sys
import tempfile

# --- Pfade --------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(HERE, "..", "..")
SPIKE_DIR = os.path.join(REPO_ROOT, "experiments", "h5_spike")

sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

import pyirk as p
from pyirk.nemobridge import export_relation_facts

# Import Test-KB setup
sys.path.insert(0, SPIKE_DIR)
from create_test_kb import setup_test_module, TEST_MOD_URI

# --- Baseline laden -----------------------------------------------------
baseline_path = os.path.join(SPIKE_DIR, "baseline_r1.json")
with open(baseline_path) as fh:
    baseline = json.load(fh)
expected_count = len(baseline)
print(f"Baseline geladen: {baseline_path}")
print(f"Erwartete R83-Eintraege (= erwartete R3-Fakten): {expected_count}")

# --- Test-KB aufbauen ---------------------------------------------------
# setup_test_module() handles register_mod + start_mod + end_mod internally.
setup_test_module()
print("Test-KB aufgebaut.")

# --- R3-Fakten exportieren ----------------------------------------------
out_dir = tempfile.mkdtemp(prefix="p1r1_verify_")
r3_csv = os.path.join(out_dir, "r3_facts.csv")

exported_count = export_relation_facts(p.ds, p.R3.uri, r3_csv, arity=2)
print(f"R3-Fakten exportiert: {exported_count} Zeilen -> {r3_csv}")

# --- Zeilen in CSV zaehlen (zur Sicherheit unabhaengig verifizieren) ----
with open(r3_csv) as fh:
    csv_lines = [ln for ln in fh if ln.strip()]
csv_count = len(csv_lines)
if csv_count != exported_count:
    print(
        f"FEHLER: Exportfunktion meldete {exported_count} Zeilen, "
        f"CSV enthaelt aber {csv_count} Zeilen.",
        file=sys.stderr,
    )
    p.unload_mod(TEST_MOD_URI, strict=False)
    sys.exit(1)

# --- Vergleich ----------------------------------------------------------
if exported_count == expected_count:
    print(f"OK: exportierte R3-Fakten ({exported_count}) == Baseline ({expected_count})")
    p.unload_mod(TEST_MOD_URI, strict=False)
    sys.exit(0)
else:
    print(
        f"FEHLER: exportierte R3-Fakten ({exported_count}) != Baseline ({expected_count})",
        file=sys.stderr,
    )
    print("Erste 10 exportierten Zeilen:", file=sys.stderr)
    for ln in csv_lines[:10]:
        print(f"  {ln.rstrip()}", file=sys.stderr)
    p.unload_mod(TEST_MOD_URI, strict=False)
    sys.exit(1)
