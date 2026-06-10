"""
pyirk.nemobridge.exporter — Generalized DataStore → Nemo-compatible CSV EDB exporter.

## CSV output convention (Phase 2.1: full-URI data columns)

Subject, predicate and object columns carry the FULL entity URI
(e.g. ``irk:/builtins#R3``, ``irk:/ocse/0.2/math#I4122``) — never the bare
short_key. This is the only way to avoid short_key collisions across modules
(Gate-1 fix). Nemo imports these as quoted strings via ``format=(string, ...)``;
see ``pyirk.nemobridge.translator``.

1. **Unqualified triples** → ``triples.csv``
   Columns: (subject_uri, predicate_uri, object_uri).
   One row per statement where *both* endpoints are Items/Relations (i.e. have
   an URI) and neither endpoint is scope-internal (see ``is_scope_internal``).
   Statements whose object is a literal are omitted.

2. **Qualified triples** → ``stmts.csv`` + ``quals_<rel_key>.csv``
   stmts.csv columns: (stmt_id, subject_uri, predicate_uri, object_uri).
   ``quals_<rel_key>.csv`` rows are (stmt_id, value); ``value`` is the qualifier
   object's full URI for entities, or repr() for literals. Filenames continue
   to use the qualifier-relation's short_key for human-readable lookup.

3. **Per-predicate files** (optional, ``per_predicate=True``)
   ``triples__<pred_key>.csv`` with (subject_uri, object_uri) columns. Filename
   keeps the short_key for human-readable lookup; cells are URIs.

4. **uri_index.csv** — audit sidecar only.
   Still written so existing audit / debugging tooling keeps working, but no
   longer the mapping path on the delegation side (V2.1: delegation resolves
   each cell directly via ``ds.get_entity_by_uri``).

## Scope-internal filter

See ``is_scope_internal`` for the precise definition and correctness conditions.
"""

import csv
import os
from collections import defaultdict
from typing import Any, Dict, Optional


def load_uri_index(out_dir) -> Dict[str, str]:
    """Read ``uri_index.csv`` from *out_dir* and return ``{short_key: uri}``.

    Audit sidecar from :func:`export_datastore`. Phase-2.1+ delegation no
    longer needs this for mapping (the data columns now carry full URIs);
    the file is kept for human-readable debugging and round-trip tests.

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
    arity:    2 → (subject_uri, object_uri)
              3 → (subject_uri, predicate_uri, object_uri)

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
            if not hasattr(s, "uri") or not hasattr(pred, "uri"):
                continue
            if not hasattr(o, "uri"):
                continue  # literal — skip for entity-only export
            if is_scope_internal(s) or is_scope_internal(o):
                continue
            if arity == 2:
                rows.append((s.uri, o.uri))
            else:
                rows.append((s.uri, pred.uri, o.uri))

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
    triples.csv          — all unqualified item-item triples; cells are full URIs
    stmts.csv            — qualified triples (reification; URIs in data cells)
    quals_<R>.csv        — one file per qualifier-relation (filename uses short_key
                           for human-readable lookup); rows are (stmt_id, value),
                           value=full URI for entities, repr() for literals.
    triples__<R>.csv     — per-predicate 2-column CSVs (only when per_predicate=True)
    uri_index.csv        — audit sidecar: (short_key, uri) for every short_key seen
                           in the exported triples. Phase-2.1+ delegation maps by
                           URI directly from the data columns; this file is no
                           longer the resolution path. Kept for human-readable
                           debugging and round-trip tests.

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
    triple_rows: list = []           # (subj_uri, pred_uri, obj_uri)
    per_pred_rows: Dict[str, list] = defaultdict(list)  # pred_key → [(s_uri, o_uri)]
    stmt_rows: list = []             # (stmt_id, subj_uri, pred_uri, obj_uri)
    qual_rows: Dict[str, list] = defaultdict(list)  # qual_rel_key → [(stmt_id, val)]
    # predicate_counts is keyed by short_key for audit readability — the
    # CSV cells carry URIs, but humans inspect counts by short_key.
    predicate_counts: Dict[str, int] = defaultdict(int)
    # uri_index is now audit-only: maps short_key → uri for every entity that
    # appears in the export. The delegation path no longer consults this file.
    uri_index: Dict[str, str] = {}

    def _record_uri(entity) -> None:
        uri = getattr(entity, "uri", None)
        if uri is None:
            return
        sk = entity.short_key
        uri_index.setdefault(sk, uri)

    for stm in _iter_subject_role_statements(ds):
        s = stm.subject
        pred = stm.predicate
        o = stm.object

        # require entity endpoints with a URI (Items/Relations always have one)
        if not hasattr(s, "uri") or not hasattr(pred, "uri"):
            continue
        if not hasattr(o, "uri"):
            continue  # literal object — excluded from entity-triple export

        if is_scope_internal(s) or is_scope_internal(o):
            continue

        s_uri = s.uri
        p_uri = pred.uri
        o_uri = o.uri
        pk = pred.short_key  # only used for per_predicate filename + counts

        _record_uri(s)
        _record_uri(pred)
        _record_uri(o)

        predicate_counts[pk] += 1

        if stm.qualifiers:
            stmt_rows.append((stm.short_key, s_uri, p_uri, o_uri))
            for qf_stm in stm.qualifiers:
                qrel = qf_stm.predicate
                if not hasattr(qrel, "short_key"):
                    continue
                _record_uri(qrel)
                qval = qf_stm.object
                if hasattr(qval, "uri"):
                    val_str = qval.uri
                    _record_uri(qval)
                else:
                    val_str = repr(qval)
                qual_rows[qrel.short_key].append((stm.short_key, val_str))
        else:
            triple_rows.append((s_uri, p_uri, o_uri))
            if per_predicate:
                per_pred_rows[pk].append((s_uri, o_uri))

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
