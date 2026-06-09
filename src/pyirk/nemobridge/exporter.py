"""
pyirk.nemobridge.exporter — Generalized DataStore → Nemo-compatible CSV EDB exporter.

## CSV output convention

All statements from `ds.statements` are partitioned into two categories:

1. **Unqualified triples** → `triples.csv`
   Columns: (subject_key, predicate_key, object_key)
   One row per statement where *both* endpoints are Items/Relations (i.e., have a
   `short_key`) and neither endpoint is scope-internal (see `is_scope_internal`).
   Statements whose object is a literal are omitted from this file (Nemo facts must
   be grounded term-only; literals may be added in a separate export if needed).

2. **Qualified triples** → `stmts.csv` + `quals_<rel_key>.csv`
   Columns of stmts.csv: (stmt_id, subject_key, predicate_key, object_key)
   One row per statement that has at least one qualifier.
   For each distinct qualifier-relation key encountered, a separate file
   `quals_<rel_key>.csv` is written with columns (stmt_id, value) where
   `value` is the short_key of the qualifier object if it is an entity, or its
   string representation if it is a literal.

   **Rationale for reification over n-ary predicates**:
   Reification (stmt_id + separate qualifier tables) was chosen over encoding
   qualifiers directly as extra columns in a wide predicate because:
   (a) different statements may have different subsets of qualifiers, so a fixed
       n-ary predicate would require many NULLs or separate rules per combination;
   (b) Nemo supports heterogeneous fact tables well; separate tables per qualifier
       relation map cleanly to Nemo predicates;
   (c) future integration (Part B) can join stmts.csv with quals_*.csv inline in
       .rls files without reshaping the export.

   **Efficiency**: statements WITHOUT qualifiers produce no row in stmts.csv.

3. **Per-predicate files** (optional, `per_predicate=True`)
   `triples__<pred_key>.csv` with columns (subject_key, object_key) — 2-column
   format suitable for Nemo when only one predicate's triples are needed.
   This mirrors the 2-column input format used in the spike (facts_for_r1.csv).

## Scope-internal filter

See `is_scope_internal` for the precise definition and correctness conditions.
"""

import csv
import os
from collections import defaultdict
from typing import Any, Dict, Optional


def load_uri_index(out_dir) -> Dict[str, str]:
    """Read ``uri_index.csv`` from *out_dir* and return ``{short_key: uri}``.

    Counterpart to :func:`export_datastore`'s V2 sidecar. The file has two
    columns (``short_key, uri``) and is written without a header row; an
    optional header (``short_key,uri``) is recognised and skipped so future
    format tweaks remain backward-compatible.

    Parameters
    ----------
    out_dir:
        Directory that contains ``uri_index.csv`` (typically the directory
        passed to :func:`export_datastore`). Accepts ``str`` or ``pathlib.Path``.

    Returns
    -------
    dict[str, str]
        Mapping ``short_key -> uri``. Empty file → empty dict.

    Raises
    ------
    FileNotFoundError
        Bubbled up by design — :func:`pyirk.nemobridge.delegation._apply_via_nemo`
        wraps the call in the silent-fallback ``try/except``.
    """
    path = os.path.join(str(out_dir), "uri_index.csv")
    result: Dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if len(row) < 2:
                continue
            short_key, uri = row[0], row[1]
            # exporter writes no header, but tolerate one if a future variant adds it
            if short_key == "short_key" and uri == "uri":
                continue
            result[short_key] = uri
    return result


def is_scope_internal(entity) -> bool:
    """Return True if *entity* is a scope-internal (prototype/template) item.

    **Definition**: An entity is scope-internal if it has at least one direct
    R20__has_defining_scope relation, i.e., `entity.get_relations(
    "R20__has_defining_scope")` returns a non-empty result.  Such entities are
    created as placeholder/pattern variables inside pyirk rule definitions (via
    the ConditionManager), and their R20 relation records to which scope
    (rule context) they belong.

    **WHEN filtered**: before exporting any triple whose subject or object is
    scope-internal — i.e., the filter applies to BOTH endpoints independently.

    **WHY correct**: scope-internal items have no independent semantic meaning
    outside their defining rule context.  They are prototypes used for
    pattern-matching within rule premises/conclusions and are NOT independent
    knowledge-base facts.  Including them in the EDB would create spurious
    triples that do not exist in the intended model.  The pyirk rule engine
    itself skips scope-internal items when applying rules to the KB.

    The spike (h5_spike_report.md, Risk 1) used the same heuristic and confirmed
    correctness for the test KB (49/49 R3 facts exported correctly).

    **BREAKS if**:
    - A scope-internal item is deliberately reused as a data-level entity
      (impossible in current pyirk design: items created in a rule scope are
      never shared with the module-level item namespace).
    - The scope semantics change so that R20 no longer reliably distinguishes
      prototype items from data items.
    - A module defines a scope-internal item that also participates in
      independent module-level statements (not gated on the same scope).

    **Why not "filter only when both endpoints share the same scope"**: the
    conservative approach (filter if EITHER endpoint is scope-internal) is
    safer.  A prototype item should never be an endpoint of a data-level triple,
    so a more permissive rule would only risk including spurious facts without
    adding correctness.
    """
    try:
        r20 = entity.get_relations("R20__has_defining_scope")
        return bool(r20)
    except Exception:
        return False


def _iter_subject_role_statements(ds):
    """Yield all subject-role Statement objects from ds.statements."""
    for _subj_uri, rel_dict in ds.statements.items():
        for _rel_uri, stm_or_list in rel_dict.items():
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                # skip inverse/qualifier statements stored via inv_statements;
                # ds.statements holds subject-role statements only
                yield stm


def export_relation_facts(ds, rel_uri: str, out_path: str, *, arity: int = 2) -> int:
    """Export all facts for a single relation as a CSV file.

    Parameters
    ----------
    ds:       pyirk DataStore
    rel_uri:  URI of the relation to export (e.g., p.R3.uri)
    out_path: output file path
    arity:    2 → (subject_key, object_key)  [default, matches spike format]
              3 → (subject_key, predicate_key, object_key)

    Returns the number of exported rows.

    Scope-internal endpoints are filtered out.  Statements whose object is a
    literal are skipped when arity=2; literal objects are not valid Nemo terms.
    """
    if arity not in (2, 3):
        raise ValueError(f"arity must be 2 or 3, got {arity}")

    rows = []
    for subj_uri, rel_dict in ds.statements.items():
        stm_or_list = rel_dict.get(rel_uri)
        if stm_or_list is None:
            continue
        stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
        for stm in stms:
            s = stm.subject
            o = stm.object
            pred = stm.predicate
            if not hasattr(s, "short_key") or not hasattr(pred, "short_key"):
                continue
            if not hasattr(o, "short_key"):
                continue  # literal — skip for entity-only export
            if is_scope_internal(s) or is_scope_internal(o):
                continue
            if arity == 2:
                rows.append((s.short_key, o.short_key))
            else:
                rows.append((s.short_key, pred.short_key, o.short_key))

    rows.sort()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="") as f:
        csv.writer(f).writerows(rows)

    return len(rows)


def export_datastore(
    ds,
    out_dir: str,
    *,
    per_predicate: bool = False,
) -> Dict[str, Any]:
    """Export the full DataStore to Nemo-compatible CSV files in *out_dir*.

    Files written
    -------------
    triples.csv          — all unqualified item-item triples
    stmts.csv            — qualified triples (reification; see module docstring)
    quals_<R>.csv        — one file per qualifier-relation key for qualified stmts
    triples__<R>.csv     — per-predicate 2-column CSVs (only when per_predicate=True)
    uri_index.csv        — (short_key, uri) sidecar index for every distinct
                           short_key that appears anywhere in the exported triples
                           (subject, predicate, object, qualifier-predicate,
                           qualifier-object). One row per short_key, sorted
                           ascending, no duplicates. Enables module-context-aware
                           reverse resolution (V2): callers must look entities up
                           by URI, not by short_key against the active module.

    Returns
    -------
    dict with keys:
      "predicate_counts"  : {pred_key: int}  — triple count per predicate
      "qualifier_counts"  : {qual_rel_key: int}  — qualifier row count per qual-relation
      "total_triples"     : int  — rows in triples.csv
      "total_qualified"   : int  — rows in stmts.csv
      "paths"             : {"triples": str, "stmts": str,
                             "quals": {rel_key: str},
                             "per_predicate": {pred_key: str},
                             "uri_index": str}
    """
    os.makedirs(out_dir, exist_ok=True)

    # --- partition statements -----------------------------------------------
    triple_rows: list = []           # (subj_key, pred_key, obj_key)
    per_pred_rows: Dict[str, list] = defaultdict(list)  # pred_key → [(s, o)]
    stmt_rows: list = []             # (stmt_id, subj_key, pred_key, obj_key)
    qual_rows: Dict[str, list] = defaultdict(list)  # qual_rel_key → [(stmt_id, val)]
    uri_index: Dict[str, str] = {}   # short_key → uri (V2)

    def _record_uri(entity) -> None:
        # entity.uri is set for every Item/Relation; skip silently otherwise
        uri = getattr(entity, "uri", None)
        if uri is None:
            return
        sk = entity.short_key
        # first occurrence wins; later entries with the same short_key would
        # only differ if two modules collided on a key, which the DataStore
        # already disallows. Keep stable for deterministic output.
        uri_index.setdefault(sk, uri)

    for stm in _iter_subject_role_statements(ds):
        s = stm.subject
        pred = stm.predicate
        o = stm.object

        # require entity endpoints with short_key
        if not hasattr(s, "short_key") or not hasattr(pred, "short_key"):
            continue
        if not hasattr(o, "short_key"):
            continue  # literal object — excluded from entity-triple export

        if is_scope_internal(s) or is_scope_internal(o):
            continue

        sk = s.short_key
        pk = pred.short_key
        ok = o.short_key

        _record_uri(s)
        _record_uri(pred)
        _record_uri(o)

        if stm.qualifiers:
            stmt_rows.append((stm.short_key, sk, pk, ok))
            for qf_stm in stm.qualifiers:
                qrel = qf_stm.predicate
                if not hasattr(qrel, "short_key"):
                    continue
                _record_uri(qrel)
                qval = qf_stm.object
                if hasattr(qval, "short_key"):
                    val_str = qval.short_key
                    _record_uri(qval)
                else:
                    val_str = repr(qval)
                qual_rows[qrel.short_key].append((stm.short_key, val_str))
        else:
            triple_rows.append((sk, pk, ok))
            if per_predicate:
                per_pred_rows[pk].append((sk, ok))

    # --- write triples.csv ---------------------------------------------------
    triple_rows.sort()
    triples_path = os.path.join(out_dir, "triples.csv")
    with open(triples_path, "w", newline="") as f:
        csv.writer(f).writerows(triple_rows)

    # --- write stmts.csv -----------------------------------------------------
    stmt_rows.sort()
    stmts_path = os.path.join(out_dir, "stmts.csv")
    with open(stmts_path, "w", newline="") as f:
        csv.writer(f).writerows(stmt_rows)

    # --- write quals_<R>.csv files -------------------------------------------
    qual_paths: Dict[str, str] = {}
    for qrel_key, rows in qual_rows.items():
        rows.sort()
        path = os.path.join(out_dir, f"quals_{qrel_key}.csv")
        with open(path, "w", newline="") as f:
            csv.writer(f).writerows(rows)
        qual_paths[qrel_key] = path

    # --- write per-predicate triples (optional) ------------------------------
    per_pred_paths: Dict[str, str] = {}
    if per_predicate:
        for pk, rows in per_pred_rows.items():
            rows.sort()
            path = os.path.join(out_dir, f"triples__{pk}.csv")
            with open(path, "w", newline="") as f:
                csv.writer(f).writerows(rows)
            per_pred_paths[pk] = path

    # --- write uri_index.csv (V2 — module-context-aware reverse resolution) --
    uri_index_path = os.path.join(out_dir, "uri_index.csv")
    with open(uri_index_path, "w", newline="") as f:
        csv.writer(f).writerows(sorted(uri_index.items()))

    # --- build audit counts --------------------------------------------------
    predicate_counts: Dict[str, int] = defaultdict(int)
    for _sid, sk, pk, ok in stmt_rows:
        predicate_counts[pk] += 1
    for sk, pk, ok in triple_rows:
        predicate_counts[pk] += 1

    qualifier_counts = {k: len(v) for k, v in qual_rows.items()}

    return {
        "predicate_counts": dict(predicate_counts),
        "qualifier_counts": qualifier_counts,
        "total_triples": len(triple_rows),
        "total_qualified": len(stmt_rows),
        "paths": {
            "triples": triples_path,
            "stmts": stmts_path,
            "quals": qual_paths,
            "per_predicate": per_pred_paths,
            "uri_index": uri_index_path,
        },
    }


if __name__ == "__main__":
    import sys
    import tempfile

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    import pyirk as p

    if len(sys.argv) > 1:
        out_dir = sys.argv[1]
    else:
        out_dir = tempfile.mkdtemp(prefix="nemobridge_")

    result = export_datastore(p.ds, out_dir, per_predicate=True)
    print(f"Exported to: {out_dir}")
    print(f"  total_triples   : {result['total_triples']}")
    print(f"  total_qualified : {result['total_qualified']}")
    print("  predicate_counts:")
    for k, v in sorted(result["predicate_counts"].items()):
        print(f"    {k}: {v}")
