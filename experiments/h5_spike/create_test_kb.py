"""
create_test_kb.py - Legt eine Test-Wissensbasis an und erfasst pyirk-Baselines fuer R1 (I64) und R2 (I66).

Standalone ausfuehrbar:
  cd /home/user/projekte/pyirk-core
  python experiments/h5_spike/create_test_kb.py
"""

import sys
import json
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
import pyirk as p

TEST_MOD_URI = "irk:/h5_spike/test_kb"
SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_test_module():
    """Registriert das Test-Modul und legt Entitaeten an."""
    km = p.KeyManager()
    p.register_mod(TEST_MOD_URI, km, check_uri=False)
    p.start_mod(TEST_MOD_URI)

    # ----- R3-Kette fuer I64 (5+ Entitaeten) -----
    # Hierarchie: I1002 -> I1001
    #             I1003 -> I1002 -> I1001
    #             I1004 -> I1003 -> I1002 -> I1001
    #             I1005 -> I1002
    I1001 = p.create_item(key_str="I1001", R1__has_label="spike_A")
    I1002 = p.create_item(key_str="I1002", R1__has_label="spike_B", R3__is_subclass_of=I1001)
    I1003 = p.create_item(key_str="I1003", R1__has_label="spike_C", R3__is_subclass_of=I1002)
    I1004 = p.create_item(key_str="I1004", R1__has_label="spike_D", R3__is_subclass_of=I1003)
    I1005 = p.create_item(key_str="I1005", R1__has_label="spike_E", R3__is_subclass_of=I1002)

    # ----- Transitive Relation fuer I66 -----
    # Erstelle eigene transitive Relation im Testmodul
    R1001 = p.create_relation(
        key_str="R1001",
        R1__has_label="spike_transitive_rel",
        R60__is_transitive=True,
    )

    # Kette: I1006 -> I1007 -> I1008 -> I1009
    I1006 = p.create_item(key_str="I1006", R1__has_label="spike_F")
    I1007 = p.create_item(key_str="I1007", R1__has_label="spike_G")
    I1008 = p.create_item(key_str="I1008", R1__has_label="spike_H")
    I1009 = p.create_item(key_str="I1009", R1__has_label="spike_I")

    I1006.set_relation(R1001, I1007)
    I1007.set_relation(R1001, I1008)
    I1008.set_relation(R1001, I1009)

    p.end_mod()

    return {
        "I1001": I1001, "I1002": I1002, "I1003": I1003, "I1004": I1004, "I1005": I1005,
        "I1006": I1006, "I1007": I1007, "I1008": I1008, "I1009": I1009,
        "R1001": R1001,
    }


def get_r83_baseline():
    """Gibt alle R83-Statements als Set von Tupeln (subj_key, pred_key, obj_key) zurueck."""
    r83_uri = p.R83.uri
    result = set()
    for subj_uri, rel_dict in p.ds.statements.items():
        for rel_uri, stm_or_list in rel_dict.items():
            if rel_uri != r83_uri:
                continue
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s = stm.subject
                o = stm.object
                if hasattr(s, "short_key") and hasattr(o, "short_key"):
                    result.add((s.short_key, "R83", o.short_key))
    return result


def get_derived_baseline_for_relation(rel):
    """Gibt alle Statements fuer 'rel' als Set von Tupeln zurueck (nur Items, keine Literale)."""
    rel_uri = rel.uri
    result = set()
    for subj_uri, rel_dict in p.ds.statements.items():
        for r_uri, stm_or_list in rel_dict.items():
            if r_uri != rel_uri:
                continue
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s = stm.subject
                o = stm.object
                if hasattr(s, "short_key") and hasattr(o, "short_key"):
                    result.add((s.short_key, rel.short_key, o.short_key))
    return result


def run_and_collect_baseline():
    """Fuehrt beide Regeln aus und sammelt die Baselines."""
    entities = setup_test_module()

    # R1 baseline: I64 anwenden (direkte R3 -> R83 Uebersetzung, kein I65)
    res_i64 = p.ruleengine.apply_semantic_rule(p.I64, mod_context_uri=TEST_MOD_URI)
    print(f"I64 erzeugte {len(res_i64.new_statements)} neue Statements")

    r83_i64_only = get_r83_baseline()
    print(f"R83-Baseline (I64 only): {len(r83_i64_only)} Statements")

    # R2 baseline: I66 exhaustiv anwenden (vollstaendige transitive Huelle)
    res_i66 = p.ruleengine.apply_semantic_rules(p.I66, mod_context_uri=TEST_MOD_URI, exhaust=True)
    print(f"I66 erzeugte {len(res_i66.new_statements)} neue Statements")

    RT = entities["R1001"]
    rt_baseline = get_derived_baseline_for_relation(RT)
    print(f"RT-Baseline gesamt: {len(rt_baseline)} Statements")

    return r83_i64_only, rt_baseline, entities


def save_baselines(r83_baseline, rt_baseline):
    """Speichert die Baselines als JSON-Dateien."""
    r83_path = os.path.join(SPIKE_DIR, "baseline_r1.json")
    rt_path = os.path.join(SPIKE_DIR, "baseline_r2.json")

    with open(r83_path, "w") as f:
        json.dump(sorted(r83_baseline), f, indent=2)
    with open(rt_path, "w") as f:
        json.dump(sorted(rt_baseline), f, indent=2)

    print(f"Baselines gespeichert: {r83_path}, {rt_path}")


def print_baselines(r83_baseline, rt_baseline):
    print("\n=== R83-Baseline (I64 only) ===")
    for t in sorted(r83_baseline):
        print(f"  {t[0]} R83 {t[2]}")

    print("\n=== RT-Baseline (I66) ===")
    for t in sorted(rt_baseline):
        print(f"  {t[0]} {t[1]} {t[2]}")


if __name__ == "__main__":
    r83_baseline, rt_baseline, entities = run_and_collect_baseline()
    print_baselines(r83_baseline, rt_baseline)
    save_baselines(r83_baseline, rt_baseline)
    p.unload_mod(TEST_MOD_URI, strict=False)
    print("\ncreate_test_kb.py: fertig.")
