#!/usr/bin/env python3
"""
p3_ocse_scale.py — P3: OCSE Skalentest für nemobridge-Delegation (Korrektheit + Timing)

Programmatisch zeigt: Delegation aller delegierbaren Regeln (direct+transitive)
auf der echten OCSE-KB erzeugt dieselbe Statement-Menge wie die pyirk-Engine.
Plus Timing-Vergleich best-of-N.

Reproduzierbarer Lauf:
  /home/user/venvs/pyirk-core-venv/bin/python experiments/h5_phase1/p3_ocse_scale.py \
      2>&1 | tee experiments/h5_phase1/p3_ocse_scale.log

Exit-Codes:
  0  — Korrektheit OK (pyirk_set == nemo_set)
  1  — Korrektheitsdiff
  2  — Infrastruktur-Fehler (Nemo nicht gefunden, OCSE nicht ladbar)

CLI-Flags:
  --repeats N     Timing-Wiederholungen (default: 3)
  --skip-timing   Timing überspringen
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter

# ─────────────────────────────────────────────────────────────────────────────
# Pfade und Konstanten
# ─────────────────────────────────────────────────────────────────────────────

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
NEMO_BIN = "/home/user/bin/nmo"
OCSE_DIR = "/home/user/projekte/irk-data/ocse"
# sympy ist nicht im pyirk-venv; neo-rag-venv hat es (gleiche Python-Version 3.13.5)
SYMPY_EXTRA = "/home/user/venvs/neo-rag-venv/lib/python3.13/site-packages"
VENV_PYTHON = "/home/user/venvs/pyirk-core-venv/bin/python"
SRC_DIR = os.path.join(REPO_ROOT, "src")
OCSE_MOD_URI = "irk:/ocse/0.2/control_theory"

# ─────────────────────────────────────────────────────────────────────────────
# Python-Pfade setzen (für diesen Prozess)
# ─────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, SYMPY_EXTRA)
sys.path.insert(0, SRC_DIR)


# ─────────────────────────────────────────────────────────────────────────────
# Load Guard
# ─────────────────────────────────────────────────────────────────────────────

def load_guard():
    """System-Last prüfen. Gibt Dict mit load1, warnings, load_burdened zurück."""
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        load1 = float(parts[0])
    except Exception:
        load1 = None

    top_proc = None
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pcpu,args", "--sort=-pcpu"],
            capture_output=True, text=True,
        )
        for line in proc.stdout.strip().splitlines()[1:]:
            cpu_str, *rest = line.strip().split(maxsplit=1)
            try:
                cpu = float(cpu_str)
            except ValueError:
                continue
            if cpu < 1.0:
                break
            cmd_str = rest[0] if rest else ""
            if "p3_ocse_scale" not in cmd_str and "claude" not in cmd_str:
                top_proc = (cpu, cmd_str[:80])
                break
    except Exception:
        pass

    load_str = f"{load1:.2f}" if load1 is not None else "N/A"
    top_str = f"{top_proc[1]} ({top_proc[0]:.1f}%)" if top_proc else "none"
    warnings_list = []
    if load1 is not None and load1 >= 0.5:
        warnings_list.append(f"load={load1:.2f}>=0.5")
    if top_proc and top_proc[0] > 50:
        warnings_list.append(f"proc={top_proc[1][:40]}@{top_proc[0]:.1f}%")

    return {
        "load1": load1,
        "load_str": load_str,
        "top_str": top_str,
        "warnings": warnings_list,
        "load_burdened": bool(warnings_list),
        "load_burdened_label": " (load-belastet)" if warnings_list else "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# OCSE laden
# ─────────────────────────────────────────────────────────────────────────────

def load_ocse():
    """Lade OCSE-KB: agents1, math1, control_theory1. Gibt pyirk zurück."""
    import pyirk as p
    p.irkloader.load_mod_from_path(
        os.path.join(OCSE_DIR, "agents1.py"), prefix="ag",
    )
    p.irkloader.load_mod_from_path(
        os.path.join(OCSE_DIR, "math1.py"), prefix="ma", reuse_loaded=True,
    )
    p.irkloader.load_mod_from_path(
        os.path.join(OCSE_DIR, "control_theory1.py"), prefix="ct", reuse_loaded=True,
    )
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 1a — Regel-Klassifikation
# ─────────────────────────────────────────────────────────────────────────────

def step1a_classify(p, out_json_path):
    """Klassifiziert alle Regeln, speichert JSON, gibt Liste zurück."""
    from pyirk.nemobridge import classify_rules, classification_to_json
    clfs = classify_rules(p.ds)

    with open(out_json_path, "w", encoding="utf-8") as f:
        f.write(classification_to_json(clfs))

    print("\n=== Schritt 1a: Regel-Klassifikation ===")
    header = f"{'Key':<8} {'Label':<50} {'Kategorie':<14} Grund (gekürzt)"
    print(header)
    print("-" * 110)
    for c in clfs:
        print(f"{c.rule_short_key:<8} {c.label[:48]:<50} {c.category:<14} {c.reason[:48]}")

    counts = Counter(c.category for c in clfs)
    print(f"\nZähler je Kategorie: {dict(counts)}")
    print(f"Gesamt: {len(clfs)} Regeln")
    print(f"JSON gespeichert: {out_json_path}")
    return clfs


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 1b — pyirk-Baseline
# ─────────────────────────────────────────────────────────────────────────────

def _stm_to_canonical(stm):
    """Statement → kanonisches 3-Tupel (s_key, p_key, o_key) oder None."""
    try:
        s, pred, o = stm.relation_tuple
        if not (hasattr(s, "short_key") and hasattr(pred, "short_key") and hasattr(o, "short_key")):
            return None
        return (s.short_key, pred.short_key, o.short_key)
    except Exception:
        return None


def _get_rule_head_preds(clfs, p):
    """
    Ermittle Prädikaten-Schlüssel, die von delegierbaren Regeln erzeugt werden.

    - direct-Regeln: Kopfprädikat aus dem rls_snippet (z.B. R83, R30)
    - transitive-Regeln: alle R60__is_transitive-Relationen (z.B. R17)

    Warum beide Typen: Der Nemo-trans-Output enthält ALLE R17-Tripel (direkte
    EDB-Fakten + abgeleitete Transitivitäts-Tripel). pyirk-new_statements enthält
    nur die NEU erzeugten. Um Vergleichbarkeit sicherzustellen, lesen wir alle
    Regelkopf-Prädikate aus ds.statements nach der Regelanwendung.
    """
    direct_heads = set()
    for clf in clfs:
        if clf.category == "direct" and clf.rls_snippet:
            for line in clf.rls_snippet.splitlines():
                line = line.strip()
                if line and not line.startswith("%") and ":-" in line:
                    head = line.split(":-")[0].strip()
                    pred_key = head.split("(")[0].strip()
                    if pred_key:
                        direct_heads.add(pred_key)

    trans_preds = set()
    for _uri, rel in p.ds.relations.items():
        try:
            if rel.R60__is_transitive:
                trans_preds.add(rel.short_key)
        except Exception:
            pass

    return direct_heads, trans_preds


def _collect_ds_triples_for_preds(p, pred_keys):
    """
    Alle Tripel aus ds.statements für die gegebenen Prädikaten-Schlüssel sammeln.
    Scope-interne Endpunkte werden (wie im Exporter) herausgefiltert.
    Literal-Objekte werden übersprungen.
    """
    from pyirk.nemobridge.exporter import is_scope_internal
    result_set = set()
    # Baue Mapping rel_short_key → rel_uri für schnellen Zugriff
    pred_uri_map = {}
    for rel_uri, rel in p.ds.relations.items():
        if hasattr(rel, "short_key") and rel.short_key in pred_keys:
            pred_uri_map[rel_uri] = rel.short_key

    for subj_uri, rel_dict in p.ds.statements.items():
        for rel_uri, stm_or_list in rel_dict.items():
            if rel_uri not in pred_uri_map:
                continue
            pred_key = pred_uri_map[rel_uri]
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s = stm.subject
                o = stm.object
                if not (hasattr(s, "short_key") and hasattr(o, "short_key")):
                    continue
                if is_scope_internal(s) or is_scope_internal(o):
                    continue
                result_set.add((s.short_key, pred_key, o.short_key))
    return result_set


def step1b_pyirk_baseline(p, clfs):
    """Delegierbare Regeln bis Fixpunkt anwenden. Gibt Set kanonischer Tupel zurück.

    Wichtig: Das Ergebnis-Set enthält ALLE Tripel der Regelkopf-Prädikate aus
    ds.statements nach der Regelanwendung — nicht nur die neu erzeugten.
    Dies entspricht dem Nemo-Output, der ebenfalls alle Tripel der Regelköpfe
    enthält (direkte EDB-Fakten + abgeleitete Fakten).
    """
    from pyirk import ruleengine

    delegatable_keys = {
        c.rule_short_key for c in clfs if c.category in ("direct", "transitive")
    }
    all_rules = ruleengine.get_all_rules()
    delegatable_rules = [r for r in all_rules if r.short_key in delegatable_keys]

    print(f"\n=== Schritt 1b: pyirk-Baseline ===")
    print(f"Delegierbare Regeln ({len(delegatable_rules)}): {sorted(r.short_key for r in delegatable_rules)}")

    direct_heads, trans_preds = _get_rule_head_preds(clfs, p)
    print(f"Direkte Regelkopf-Prädikate: {sorted(direct_heads)}")
    print(f"Transitive Prädikate (R60__is_transitive): {sorted(trans_preds)}")
    all_head_preds = direct_heads | trans_preds

    result = ruleengine.apply_semantic_rules(
        *delegatable_rules,
        mod_context_uri=OCSE_MOD_URI,
        exhaust=True,
    )
    print(f"Neue Statements erzeugt: {len(result.new_statements)}")

    # Kanonische Tupel aufbauen:
    # (A) Neu abgeleitete Statements (result.new_statements): deckt direkte Regel-Köpfe ab
    #     (R83, R30 falls abgeleitet). Vorher existierende Basis-Fakten dieser Prädikate
    #     werden NICHT mitgezählt (sie stehen nicht im Nemo-R30/R83-IDB-Output).
    pyirk_set = set()
    skipped_literal = 0
    for stm in result.new_statements:
        tup = _stm_to_canonical(stm)
        if tup is not None:
            pyirk_set.add(tup)
        else:
            skipped_literal += 1

    # (B) Alle trans-Prädikate aus ds.statements (basis + abgeleitet):
    #     Nemos output_trans.csv enthält ALLE Tripel transitiver Prädikate
    #     (Basisfakten via trans-Basisregel + abgeleitete). Deshalb müssen wir
    #     hier alle R17-Tripel aus ds.statements aufnehmen.
    base_trans_triples = _collect_ds_triples_for_preds(p, trans_preds)
    pyirk_set |= base_trans_triples

    print(f"Neu abgeleitet (new_statements, inkl. R83): {len(result.new_statements) - skipped_literal}")
    print(f"Trans-Basis + -Abgeleitet (ds.statements für {sorted(trans_preds)}): {len(base_trans_triples)}")
    print(f"Kanonische Tupel gesamt: {len(pyirk_set)}")
    print(f"Übersprungen (Literal/kein Entity in new_statements): {skipped_literal}")
    print("Hinweis: Qualifier ignoriert (Translator produziert keine Qualifier-Fakten).")
    print("Hinweis: Vorher existierende direkte Fakten (z.B. OCSE-basis-R30) werden nicht mitgezählt.")
    pred_counts = Counter(t[1] for t in pyirk_set)
    print(f"Nach Prädikat: {dict(sorted(pred_counts.items()))}")
    return pyirk_set


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 1c — Nemo-Pfad
# ─────────────────────────────────────────────────────────────────────────────

def _run_nemo(rls_path, import_dir, export_dir):
    os.makedirs(export_dir, exist_ok=True)
    cmd = [
        NEMO_BIN,
        "--export-dir", export_dir,
        "--import-dir", import_dir,
        "--overwrite-results",
        rls_path,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def _parse_nemo_outputs(export_dir):
    """Alle output_*.csv lesen → Set kanonischer 3-Tupel."""
    nemo_set = set()
    files_found = []
    for fname in sorted(os.listdir(export_dir)):
        if not (fname.startswith("output_") and fname.endswith(".csv")):
            continue
        files_found.append(fname)
        fpath = os.path.join(export_dir, fname)
        if fname == "output_trans.csv":
            # 3-spaltig: (subj, pred, obj)
            with open(fpath, newline="") as f:
                for row in csv.reader(f):
                    if len(row) >= 3:
                        nemo_set.add((row[0], row[1], row[2]))
        else:
            # 2-spaltig: Prädikat aus Dateiname ableiten
            pred_key = fname[len("output_"):-len(".csv")]
            with open(fpath, newline="") as f:
                for row in csv.reader(f):
                    if len(row) >= 2:
                        nemo_set.add((row[0], pred_key, row[1]))
    return nemo_set, files_found


def step1c_nemo_path(edb_dir, p, nemo_work_dir):
    """Nemo auf vorexportierter Roh-EDB ausführen. Gibt kanonische Tupel zurück."""
    from pyirk.nemobridge import generate_rls

    print(f"\n=== Schritt 1c: Nemo-Pfad ===")
    print(f"EDB-Dir (Roh, vor pyirk-Regeln): {edb_dir}")

    rls = generate_rls(p.ds)
    rls_path = os.path.join(nemo_work_dir, "rules.rls")
    with open(rls_path, "w") as f:
        f.write(rls)
    print(f"RLS geschrieben: {rls_path}")

    print("--- RLS-Inhalt ---")
    for line in rls.splitlines():
        print(f"  {line}")
    print("--- Ende RLS ---")

    nemo_out_dir = os.path.join(nemo_work_dir, "nemo_out")
    proc = _run_nemo(rls_path, edb_dir, nemo_out_dir)
    if proc.returncode != 0:
        print(f"FEHLER: Nemo exit {proc.returncode}", file=sys.stderr)
        print(proc.stderr[:2000], file=sys.stderr)
        return None, None

    nemo_set, files = _parse_nemo_outputs(nemo_out_dir)
    print(f"Output-Dateien: {files}")
    print(f"Kanonische Tupel: {len(nemo_set)}")
    pred_counts = Counter(t[1] for t in nemo_set)
    print(f"Nach Prädikat: {dict(sorted(pred_counts.items()))}")
    return nemo_set, nemo_out_dir


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 1d — Vergleich
# ─────────────────────────────────────────────────────────────────────────────

def step1d_compare(pyirk_set, nemo_set):
    """Sets vergleichen. Gibt (ok, diff_info) zurück."""
    print(f"\n=== Schritt 1d: Vergleich ===")
    print(f"pyirk: {len(pyirk_set)} Tupel  |  nemo: {len(nemo_set)} Tupel")

    ok = pyirk_set == nemo_set
    only_pyirk = sorted(pyirk_set - nemo_set)
    only_nemo = sorted(nemo_set - pyirk_set)

    if ok:
        print(f"IDENTISCH: {len(pyirk_set)} Tupel stimmen exakt überein")
    else:
        print(f"DIFF ERKANNT:")
        print(f"  Nur in pyirk ({len(only_pyirk)} gesamt):")
        for t in only_pyirk[:20]:
            print(f"    {t}")
        if len(only_pyirk) > 20:
            print(f"    ... und {len(only_pyirk) - 20} weitere")
        print(f"  Nur in nemo ({len(only_nemo)} gesamt):")
        for t in only_nemo[:20]:
            print(f"    {t}")
        if len(only_nemo) > 20:
            print(f"    ... und {len(only_nemo) - 20} weitere")

    return ok, {
        "n_only_pyirk": len(only_pyirk),
        "n_only_nemo": len(only_nemo),
        "sample_only_pyirk": only_pyirk[:5],
        "sample_only_nemo": only_nemo[:5],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Schritt 1e — Timing (Subprozesse für frischen Zustand)
# ─────────────────────────────────────────────────────────────────────────────

_PYIRK_TIMING_SCRIPT = '''\
import sys, time, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, {sympy_extra!r})
sys.path.insert(0, {src_dir!r})

import pyirk as p
import pyirk.ruleengine as re_mod

ocse_dir = {ocse_dir!r}
ocse_uri = {ocse_uri!r}

p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "agents1.py"), prefix="ag")
p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "math1.py"), prefix="ma", reuse_loaded=True)
p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "control_theory1.py"), prefix="ct", reuse_loaded=True)

from pyirk.nemobridge import classify_rules
clfs = classify_rules(p.ds)
delegatable_keys = {{c.rule_short_key for c in clfs if c.category in ("direct", "transitive")}}
delegatable_rules = [r for r in re_mod.get_all_rules() if r.short_key in delegatable_keys]

t0 = time.perf_counter()
re_mod.apply_semantic_rules(*delegatable_rules, mod_context_uri=ocse_uri, exhaust=True)
t1 = time.perf_counter()
print(f"{{t1 - t0:.6f}}")
'''

_NEMO_TIMING_SCRIPT = '''\
import sys, time, os, subprocess, csv, tempfile, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, {sympy_extra!r})
sys.path.insert(0, {src_dir!r})

import pyirk as p

ocse_dir = {ocse_dir!r}
nemo_bin = {nemo_bin!r}

p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "agents1.py"), prefix="ag")
p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "math1.py"), prefix="ma", reuse_loaded=True)
p.irkloader.load_mod_from_path(os.path.join(ocse_dir, "control_theory1.py"), prefix="ct", reuse_loaded=True)

from pyirk.nemobridge import export_datastore, generate_rls

tmp_dir = tempfile.mkdtemp(prefix="nemo_time_")
nemo_out_dir = os.path.join(tmp_dir, "out")
os.makedirs(nemo_out_dir, exist_ok=True)

# Pipeline messen: Export + RLS-Codegen + nmo-Run + Output-Parse
t0 = time.perf_counter()

export_datastore(p.ds, tmp_dir)
rls = generate_rls(p.ds)
rls_path = os.path.join(tmp_dir, "rules.rls")
with open(rls_path, "w") as f:
    f.write(rls)

cmd = [nemo_bin, "--export-dir", nemo_out_dir, "--import-dir", tmp_dir,
       "--overwrite-results", rls_path]
proc = subprocess.run(cmd, capture_output=True, text=True)
if proc.returncode != 0:
    print("NEMO_ERROR", proc.stderr[:200], file=sys.stderr)
    sys.exit(1)

nemo_set = set()
for fname in os.listdir(nemo_out_dir):
    if not (fname.startswith("output_") and fname.endswith(".csv")):
        continue
    fpath = os.path.join(nemo_out_dir, fname)
    if fname == "output_trans.csv":
        with open(fpath, newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 3:
                    nemo_set.add((row[0], row[1], row[2]))
    else:
        pred_key = fname[len("output_"):-len(".csv")]
        with open(fpath, newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    nemo_set.add((row[0], pred_key, row[1]))

t1 = time.perf_counter()
print(f"{{t1 - t0:.6f}}")
'''


def _run_timing_subprocess(script_text, label=""):
    """Timing-Skript in Subprozess ausführen. Gibt float oder None zurück."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(script_text)
        fpath = f.name
    try:
        proc = subprocess.run(
            [VENV_PYTHON, fpath],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            print(f"  [{label}] Subprozess-Fehler (exit {proc.returncode}): {proc.stderr[:300]}",
                  file=sys.stderr)
            return None
        lines = proc.stdout.strip().splitlines()
        if not lines:
            return None
        return float(lines[-1].strip())
    except Exception as e:
        print(f"  [{label}] Exception: {e}", file=sys.stderr)
        return None
    finally:
        os.unlink(fpath)


def step1e_timing(repeats):
    """Timing: repeats Subprozesse für pyirk und Nemo. Gibt Dict zurück."""
    print(f"\n=== Schritt 1e: Timing (best-of-{repeats}) ===")
    print("pyirk misst: apply_semantic_rules(*delegatable, exhaust=True)")
    print("Nemo misst:  export_datastore + generate_rls + nmo-Run + Output-Parse")

    pyirk_script = _PYIRK_TIMING_SCRIPT.format(
        sympy_extra=SYMPY_EXTRA, src_dir=SRC_DIR,
        ocse_dir=OCSE_DIR, ocse_uri=OCSE_MOD_URI,
    )
    nemo_script = _NEMO_TIMING_SCRIPT.format(
        sympy_extra=SYMPY_EXTRA, src_dir=SRC_DIR,
        ocse_dir=OCSE_DIR, nemo_bin=NEMO_BIN,
    )

    pyirk_times = []
    nemo_times = []
    load_burdened_events = []

    print(f"\n--- pyirk: {repeats} Runs (jeweils frischer Subprozess) ---")
    for i in range(repeats):
        lg = load_guard()
        if lg["load_burdened"]:
            warn = ", ".join(lg["warnings"])
            print(f"  Run {i+1}: LAST-WARNUNG [{warn}] — messe trotzdem")
            load_burdened_events.append(f"pyirk-run{i+1}: {warn}")
        t = _run_timing_subprocess(pyirk_script, label=f"pyirk-run{i+1}")
        if t is not None:
            pyirk_times.append(t)
            print(f"  Run {i+1}: {t:.4f}s")
        else:
            print(f"  Run {i+1}: FEHLER")

    print(f"\n--- Nemo: {repeats} Runs (jeweils frischer Subprozess) ---")
    for i in range(repeats):
        lg = load_guard()
        if lg["load_burdened"]:
            warn = ", ".join(lg["warnings"])
            print(f"  Run {i+1}: LAST-WARNUNG [{warn}] — messe trotzdem")
            load_burdened_events.append(f"nemo-run{i+1}: {warn}")
        t = _run_timing_subprocess(nemo_script, label=f"nemo-run{i+1}")
        if t is not None:
            nemo_times.append(t)
            print(f"  Run {i+1}: {t:.4f}s")
        else:
            print(f"  Run {i+1}: FEHLER")

    if not pyirk_times or not nemo_times:
        print("FEHLER: Timing unvollständig", file=sys.stderr)
        return None

    pyirk_best = min(pyirk_times)
    nemo_best = min(nemo_times)
    speedup = pyirk_best / nemo_best if nemo_best > 0 else float("inf")

    print(f"\n--- Timing-Ergebnis ---")
    print(f"pyirk Runs: {[f'{t:.4f}s' for t in pyirk_times]}  Best: {pyirk_best:.4f}s")
    print(f"Nemo  Runs: {[f'{t:.4f}s' for t in nemo_times]}  Best: {nemo_best:.4f}s")
    print(f"Speedup (t_pyirk_best / t_nemo_best): {speedup:.2f}x")

    return {
        "pyirk_times": pyirk_times,
        "nemo_times": nemo_times,
        "pyirk_best": pyirk_best,
        "nemo_best": nemo_best,
        "speedup": speedup,
        "load_burdened": bool(load_burdened_events),
        "load_burdened_events": load_burdened_events,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Hauptprogramm
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="P3 OCSE Skalentest: nemobridge vs pyirk-Engine"
    )
    parser.add_argument(
        "--repeats", type=int, default=3,
        help="Timing-Wiederholungen (best-of-N, default: 3)",
    )
    parser.add_argument(
        "--skip-timing", action="store_true",
        help="Timing-Messung überspringen",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("H5 Phase 1 — P3: OCSE Skalentest (Korrektheit + Timing)")
    print("=" * 70)

    # ── Pre-flight ────────────────────────────────────────────────────────────
    print("\n=== Pre-flight ===")
    lg_pre = load_guard()
    print(f"uptime load (1-min): {lg_pre['load_str']}")
    print(f"Top-CPU-Prozess: {lg_pre['top_str']}")
    for w in lg_pre["warnings"]:
        print(f"  WARNUNG: {w}")

    # Nemo-Binary prüfen
    if not os.path.isfile(NEMO_BIN):
        print(f"FEHLER: Nemo-Binary nicht gefunden: {NEMO_BIN}", file=sys.stderr)
        sys.exit(2)
    proc = subprocess.run([NEMO_BIN, "--version"], capture_output=True, text=True)
    nemo_version = (proc.stdout + proc.stderr).strip().split("\n")[0]
    print(f"Nemo: {nemo_version}")

    # ── OCSE laden ────────────────────────────────────────────────────────────
    print("\n=== OCSE laden ===")
    t0 = time.perf_counter()
    try:
        p = load_ocse()
    except Exception as e:
        print(f"FEHLER beim OCSE-Laden: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)
    load_time = time.perf_counter() - t0
    print(f"OCSE geladen in {load_time:.2f}s")

    # ── EDB exportieren VOR Regelanwendung ───────────────────────────────────
    raw_edb_dir = tempfile.mkdtemp(prefix="h5p3_raw_edb_")
    nemo_work_dir = tempfile.mkdtemp(prefix="h5p3_nemo_work_")
    print(f"\nRoh-EDB-Verzeichnis: {raw_edb_dir}")
    print(f"Nemo-Arbeitsverzeichnis: {nemo_work_dir}")

    from pyirk.nemobridge import export_datastore
    audit = export_datastore(p.ds, raw_edb_dir)
    print(f"Roh-EDB: {audit['total_triples']} Tripel (unqualifiziert)")
    print(f"         {audit['total_qualified']} qualifizierte Statements")
    print(f"Prädikaten-Zähler (Top-10 nach Häufigkeit):")
    for pk, cnt in sorted(audit["predicate_counts"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {pk}: {cnt}")

    # ── Schritt 1a: Klassifikation ───────────────────────────────────────────
    json_path = os.path.join(HERE, "p3_rule_classification.json")
    clfs = step1a_classify(p, json_path)

    # ── Schritt 1b: pyirk-Baseline ───────────────────────────────────────────
    pyirk_set = step1b_pyirk_baseline(p, clfs)

    # ── Schritt 1c: Nemo-Pfad (auf Roh-EDB) ─────────────────────────────────
    nemo_set, nemo_out_dir = step1c_nemo_path(raw_edb_dir, p, nemo_work_dir)
    if nemo_set is None:
        print("FEHLER: Nemo-Lauf fehlgeschlagen → Exit 1", file=sys.stderr)
        sys.exit(1)

    # ── Schritt 1d: Vergleich ────────────────────────────────────────────────
    ok, diff_info = step1d_compare(pyirk_set, nemo_set)

    # ── Schritt 1e: Timing ───────────────────────────────────────────────────
    timing = None
    if not args.skip_timing:
        timing = step1e_timing(args.repeats)

    # ── Post-flight ──────────────────────────────────────────────────────────
    print("\n=== Post-flight ===")
    lg_post = load_guard()
    print(f"Load (1-min): {lg_post['load_str']}, Top-Prozess: {lg_post['top_str']}")

    # ── Verdict ──────────────────────────────────────────────────────────────
    corr_str = "ja" if ok else "nein"
    if timing:
        speedup_int = round(timing["speedup"])
        load_sfx = timing["load_burdened_events"][0][:30] if timing["load_burdened"] else ""
        load_label = f" (load-belastet, {load_sfx})" if timing["load_burdened"] else ""
        verdict = (
            f"P3-VERDICT: ocse_korrekt={corr_str} "
            f"speedup_test_e01={speedup_int}x{load_label}"
        )
    else:
        verdict = f"P3-VERDICT: ocse_korrekt={corr_str} speedup_test_e01=N/A (--skip-timing)"

    print(f"\n{'=' * 70}")
    print(verdict)
    print(f"{'=' * 70}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
