"""
exporter.py - pyirk DataStore -> Nemo-kompatible CSV-Fakten

Importierbar und standalone ausfuehrbar.
"""

import sys
import os
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))


def is_scope_item(entity) -> bool:
    """Gibt True zurueck wenn es ein Scope-/Prototype-Item ist (hat R20__has_defining_scope)."""
    try:
        r20 = entity.get_relations("R20__has_defining_scope")
        return bool(r20)
    except Exception:
        return False


def export_r3_facts(ds, out_path: str) -> int:
    """
    Exportiert alle R3__is_subclass_of Fakten als 2-spaltige CSV (subj, obj).
    Nur nicht-Scope-Items mit item-artigen Objekten.

    Gibt die Anzahl exportierter Fakten zurueck.
    """
    import pyirk as p
    r3_uri = p.R3.uri
    rows = []

    for subj_uri, rel_dict in ds.statements.items():
        for rel_uri, stm_or_list in rel_dict.items():
            if rel_uri != r3_uri:
                continue
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s = stm.subject
                o = stm.object
                if not hasattr(s, "short_key") or not hasattr(o, "short_key"):
                    continue
                if is_scope_item(s) or is_scope_item(o):
                    continue
                rows.append((s.short_key, o.short_key))

    rows.sort()
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return len(rows)


def export_transitive_triple_facts(ds, transitive_rel, out_path: str) -> int:
    """
    Exportiert alle Tripel (subj, rel_key, obj) fuer die gegebene transitive Relation.
    Format: 3-spaltige CSV (subj_key, rel_key, obj_key).

    Gibt die Anzahl exportierter Fakten zurueck.
    """
    rel_uri = transitive_rel.uri
    rows = []

    for subj_uri, rel_dict in ds.statements.items():
        for r_uri, stm_or_list in rel_dict.items():
            if r_uri != rel_uri:
                continue
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s = stm.subject
                o = stm.object
                if not hasattr(s, "short_key") or not hasattr(o, "short_key"):
                    continue
                if is_scope_item(s) or is_scope_item(o):
                    continue
                rows.append((s.short_key, transitive_rel.short_key, o.short_key))

    rows.sort()
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return len(rows)


def export_all_triples(ds, out_path: str) -> int:
    """
    Exportiert ALLE Tripel (subj_key, pred_key, obj_key) aus dem DataStore.
    Filtert Scope-Items und Literal-Objekte heraus.
    """
    rows = []

    for subj_uri, rel_dict in ds.statements.items():
        for rel_uri, stm_or_list in rel_dict.items():
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s = stm.subject
                p_rel = stm.predicate
                o = stm.object
                if not hasattr(s, "short_key") or not hasattr(p_rel, "short_key"):
                    continue
                if not hasattr(o, "short_key"):
                    continue
                if is_scope_item(s) or is_scope_item(o):
                    continue
                rows.append((s.short_key, p_rel.short_key, o.short_key))

    rows.sort()
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return len(rows)


if __name__ == "__main__":
    import pyirk as p
    from create_test_kb import setup_test_module, TEST_MOD_URI

    km = p.KeyManager()
    p.register_mod(TEST_MOD_URI, km, check_uri=False)
    entities = setup_test_module()
    # end_mod is called inside setup_test_module

    r1_csv = os.path.join(SPIKE_DIR, "facts_for_r1.csv")
    r2_csv = os.path.join(SPIKE_DIR, "facts_for_r2.csv")

    n1 = export_r3_facts(p.ds, r1_csv)
    print(f"R3-Fakten exportiert: {n1} -> {r1_csv}")

    RT = entities["R1001"]
    n2 = export_transitive_triple_facts(p.ds, RT, r2_csv)
    print(f"Transitive-Tripel exportiert: {n2} -> {r2_csv}")

    p.unload_mod(TEST_MOD_URI, strict=False)
    print("exporter.py: fertig.")
