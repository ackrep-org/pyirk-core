"""Structural per-snippet diff between a gold pyirk module and a candidate.

Operates on pyirk module source text via :mod:`ast` -- never ``exec`` -- and
produces a label-keyed, reuse-tolerant multiset diff per snippet.  Used in the
``fnl_vs_direct`` experiment to check whether a directly generated pyirk
module reproduces the structural content of the corpus-A (``nichtlinear``)
gold module.

The bucketing rule:

* A ``snippet(N)`` marker is a top-level ``p.create_item`` call whose
  ``R1__has_label`` value matches ``snippet(<id>)``.  ``<id>`` may be a plain
  integer (e.g. ``"3"``) or an ignored marker (e.g. ``"1i"``).
* Declarations between marker N and marker M (exclusive) belong to snippet N.
* The marker item itself belongs to its own snippet bucket.
* Declarations before the first marker land in the ``_prelude`` bucket.
* ``update_relations`` / ``set_relation`` calls targeting a locally declared
  entity merge their R-keyword payload into that entity's ``extra`` dict.
* The same calls targeting an external entity (``p.I35[...]``, ``ma.I5166[...]``)
  create a synthetic :class:`ItemRec` in the current snippet bucket so the
  decoration is captured.  Its ``key`` is the dotted-name reference (e.g.
  ``"p.I35"``) and its ``label`` is the subscript string.

The diff matches by R1 label (case- and whitespace-normalised).  Keys can
freely differ between gold and direct: the matching is structural.  An
optional ``reuse_index`` maps labels to existing OCSE keys so a direct module
that re-uses an OCSE item via reference instead of redeclaring it is not
flagged as a duplicate.

CLI:

    python -m experiments.fnl_vs_direct.structural_diff \\
        --gold gold.py --direct direct.py \\
        (--snippets 3,4,5 | --selection snippet_selection.json) \\
        --out out.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union


SNIPPET_RE = re.compile(r"^snippet\(([^)]+)\)$")


# ---------------------------------------------------------------------------
# Data classes


@dataclass
class ItemRec:
    key: str
    label: str
    extra: Dict[str, Union[str, List[str]]] = field(default_factory=dict)


@dataclass
class RelRec:
    key: str
    label: str
    extra: Dict[str, Union[str, List[str]]] = field(default_factory=dict)


@dataclass
class SnippetBlock:
    snippet_id: str
    items: List[ItemRec] = field(default_factory=list)
    relations: List[RelRec] = field(default_factory=list)


@dataclass
class ModuleSummary:
    prelude_items: List[ItemRec] = field(default_factory=list)
    prelude_relations: List[RelRec] = field(default_factory=list)
    by_snippet: Dict[str, SnippetBlock] = field(default_factory=dict)


@dataclass
class SnippetDiff:
    snippet_id: str
    missing_items: List[str] = field(default_factory=list)
    extra_items: List[str] = field(default_factory=list)
    mismatched_relations: List[Tuple[str, str, str, str]] = field(default_factory=list)
    missing_relations: List[Tuple[str, str]] = field(default_factory=list)
    extra_relations: List[Tuple[str, str]] = field(default_factory=list)
    score: float = 0.0


# ---------------------------------------------------------------------------
# AST helpers


def _dotted_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        if prefix is None:
            return None
        return f"{prefix}.{node.attr}"
    return None


def _const_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _value_to_str(node: ast.AST) -> Union[str, List[str]]:
    """Normalise an AST value node to a string (or list of strings).

    The goal is structural identity, not perfect fidelity: subscript
    references (``p.I35["real number"]``) collapse to their label so two
    modules using different key allocations still compare equal on content.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        return repr(node.value)
    if isinstance(node, ast.Subscript):
        label = _const_str(node.slice)
        if label is not None:
            return label
        return ast.unparse(node)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _dotted_name(node) or ast.unparse(node)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_flatten(_value_to_str(elt)) for elt in node.elts]
    return ast.unparse(node)


def _flatten(v: Union[str, List[str]]) -> str:
    if isinstance(v, list):
        return "[" + ",".join(v) + "]"
    return v


def _is_create_item_call(call: ast.Call) -> bool:
    fn = _dotted_name(call.func)
    return fn is not None and fn.endswith(".create_item") or fn == "create_item"


def _is_create_relation_call(call: ast.Call) -> bool:
    fn = _dotted_name(call.func)
    return fn is not None and fn.endswith(".create_relation") or fn == "create_relation"


def _extract_r_key(keyword_name: str) -> Optional[str]:
    # Examples: R1__has_label, R3__is_subclass_of, ma__R7280__has_element_type.
    # Return the canonical R-id (R<digits>).  If there is a non-numeric prefix
    # (e.g. ``ma__R7280``), prepend it -- different prefixes are different
    # relations.
    parts = keyword_name.split("__")
    rkey = None
    prefix = None
    for part in parts:
        if re.match(r"^R\d+$", part):
            rkey = part
            break
        if rkey is None and part:
            prefix = part if prefix is None else prefix  # only first prefix
    if rkey is None:
        return None
    if prefix is not None and not re.match(r"^R\d+$", prefix):
        return f"{prefix}__{rkey}"
    return rkey


def _kwargs_to_extra(call: ast.Call, skip_r1: bool = True) -> Dict[str, Union[str, List[str]]]:
    extra: Dict[str, Union[str, List[str]]] = {}
    for kw in call.keywords:
        if kw.arg is None:  # **kwargs
            continue
        rkey = _extract_r_key(kw.arg)
        if rkey is None:
            continue
        if skip_r1 and rkey == "R1":
            continue
        val = _value_to_str(kw.value)
        if isinstance(val, list):
            extra[rkey] = [str(x) for x in val]
        else:
            extra[rkey] = str(val)
    return extra


def _r1_label(call: ast.Call) -> Optional[str]:
    for kw in call.keywords:
        if kw.arg is None:
            continue
        if _extract_r_key(kw.arg) == "R1":
            v = _value_to_str(kw.value)
            if isinstance(v, str):
                return v
    return None


# ---------------------------------------------------------------------------
# Module parsing


def parse_pyirk_module(source: str) -> ModuleSummary:
    """Parse a pyirk module source string into a :class:`ModuleSummary`."""

    tree = ast.parse(source)
    summary = ModuleSummary()

    current_snippet: Optional[str] = None
    item_index: Dict[str, ItemRec] = {}
    rel_index: Dict[str, RelRec] = {}

    def bucket_for_decl(snippet_id: Optional[str], kind: str) -> List:
        if snippet_id is None:
            return summary.prelude_items if kind == "item" else summary.prelude_relations
        block = summary.by_snippet.setdefault(snippet_id, SnippetBlock(snippet_id=snippet_id))
        return block.items if kind == "item" else block.relations

    def synth_bucket(snippet_id: Optional[str]) -> Optional[SnippetBlock]:
        if snippet_id is None:
            return None
        return summary.by_snippet.setdefault(snippet_id, SnippetBlock(snippet_id=snippet_id))

    for stmt in tree.body:
        # --- top-level assignments: declarations ------------------------
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if not (isinstance(call.func, (ast.Attribute, ast.Name))):
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            target_key = stmt.targets[0].id

            if _is_create_item_call(call):
                label = _r1_label(call) or ""
                extras = _kwargs_to_extra(call, skip_r1=True)
                marker = SNIPPET_RE.match(label)
                if marker:
                    sid = marker.group(1)
                    current_snippet = sid
                    block = summary.by_snippet.setdefault(sid, SnippetBlock(snippet_id=sid))
                    rec = ItemRec(key=target_key, label=label, extra=extras)
                    block.items.append(rec)
                else:
                    rec = ItemRec(key=target_key, label=label, extra=extras)
                    bucket_for_decl(current_snippet, "item").append(rec)
                item_index[target_key] = rec
                continue

            if _is_create_relation_call(call):
                label = _r1_label(call) or ""
                extras = _kwargs_to_extra(call, skip_r1=True)
                rec = RelRec(key=target_key, label=label, extra=extras)
                bucket_for_decl(current_snippet, "rel").append(rec)
                rel_index[target_key] = rec
                continue

        # --- top-level expressions: relation-setting calls --------------
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if not isinstance(call.func, ast.Attribute):
                continue
            method = call.func.attr
            if method == "update_relations":
                target = call.func.value
                base, sub_label = _resolve_subscript_target(target)
                if base is None:
                    continue
                extras = _kwargs_to_extra(call, skip_r1=False)
                _attach_extras(
                    base,
                    sub_label,
                    extras,
                    item_index,
                    rel_index,
                    summary,
                    current_snippet,
                )
                continue

            if method == "set_relation":
                target = call.func.value
                base, sub_label = _resolve_subscript_target(target)
                if base is None or len(call.args) < 2:
                    continue
                rkey = _resolve_relation_arg(call.args[0])
                if rkey is None:
                    continue
                val = _value_to_str(call.args[1])
                val_str = _flatten(val)
                _attach_extras(
                    base,
                    sub_label,
                    {rkey: val_str},
                    item_index,
                    rel_index,
                    summary,
                    current_snippet,
                )
                continue

    return summary


def _resolve_subscript_target(node: ast.AST) -> Tuple[Optional[str], Optional[str]]:
    if isinstance(node, ast.Subscript):
        base = _dotted_name(node.value)
        label = _const_str(node.slice)
        return base, label
    base = _dotted_name(node)
    return base, None


def _resolve_relation_arg(node: ast.AST) -> Optional[str]:
    """For ``set_relation(p.R3["is subclass of"], ...)`` return ``"R3"``.

    Falls back to extracting the R-id from the dotted name if no subscript
    label is available.
    """
    if isinstance(node, ast.Subscript):
        base = _dotted_name(node.value)
        if base is not None:
            tail = base.rsplit(".", 1)[-1]
            m = re.match(r"^(R\d+)$", tail)
            if m:
                return m.group(1)
    base = _dotted_name(node)
    if base is None:
        return None
    tail = base.rsplit(".", 1)[-1]
    m = re.match(r"^(R\d+)$", tail)
    return m.group(1) if m else None


def _attach_extras(
    base: str,
    sub_label: Optional[str],
    extras: Dict[str, Union[str, List[str]]],
    item_index: Dict[str, ItemRec],
    rel_index: Dict[str, RelRec],
    summary: ModuleSummary,
    current_snippet: Optional[str],
) -> None:
    if base in item_index:
        _merge_extras(item_index[base].extra, extras)
        return
    if base in rel_index:
        _merge_extras(rel_index[base].extra, extras)
        return
    # External reference: synthesise a record in the current bucket.
    if sub_label is None:
        return
    if current_snippet is None:
        # prelude
        if base.rsplit(".", 1)[-1].startswith("R"):
            rec = RelRec(key=base, label=sub_label, extra=dict(extras))
            summary.prelude_relations.append(rec)
        else:
            rec = ItemRec(key=base, label=sub_label, extra=dict(extras))
            summary.prelude_items.append(rec)
        return
    block = summary.by_snippet.setdefault(current_snippet, SnippetBlock(snippet_id=current_snippet))
    if base.rsplit(".", 1)[-1].startswith("R"):
        rec = RelRec(key=base, label=sub_label, extra=dict(extras))
        block.relations.append(rec)
    else:
        rec = ItemRec(key=base, label=sub_label, extra=dict(extras))
        block.items.append(rec)


def _merge_extras(
    dest: Dict[str, Union[str, List[str]]],
    src: Dict[str, Union[str, List[str]]],
) -> None:
    for k, v in src.items():
        dest[k] = v


# ---------------------------------------------------------------------------
# Diff


def _norm_label(s: str) -> str:
    return " ".join(s.strip().split()).lower()


def _empty_block(snippet_id: str) -> SnippetBlock:
    return SnippetBlock(snippet_id=snippet_id)


def diff_snippet(
    gold: SnippetBlock,
    direct: SnippetBlock,
    reuse_index: Optional[Dict[str, str]] = None,
) -> SnippetDiff:
    """Compare two snippet blocks by R1 label.

    ``score = 1 - (n_missing + n_extra + n_mismatched) / max(1, n_gold_total)``
    where ``n_gold_total`` is the count of gold items plus gold relations
    plus the total number of R-keys recorded across them.
    """

    reuse_index = reuse_index or {}

    def by_label(recs: List) -> Dict[str, List]:
        out: Dict[str, List] = {}
        for r in recs:
            out.setdefault(_norm_label(r.label), []).append(r)
        return out

    snippet_id = gold.snippet_id or direct.snippet_id

    # ---- items -----------------------------------------------------------
    g_items = by_label(gold.items)
    d_items = by_label(direct.items)
    g_rels = by_label(gold.relations)
    d_rels = by_label(direct.relations)

    missing_items: List[str] = []
    extra_items: List[str] = []
    mismatched_relations: List[Tuple[str, str, str, str]] = []
    missing_relations: List[Tuple[str, str]] = []
    extra_relations: List[Tuple[str, str]] = []

    n_gold_total = 0
    for recs in g_items.values():
        n_gold_total += len(recs)
        for rec in recs:
            n_gold_total += len(rec.extra)
    for recs in g_rels.values():
        n_gold_total += len(recs)
        for rec in recs:
            n_gold_total += len(rec.extra)

    # Items: match by label (case-/ws-normalised).  Reuse_index hints that
    # a missing gold label may legally be absent from direct (it was reused
    # via an external OCSE reference).
    consumed_d_items: Dict[str, int] = {label: 0 for label in d_items}

    for label_norm, g_recs in g_items.items():
        d_recs = d_items.get(label_norm, [])
        # Pair up.
        n_g = len(g_recs)
        n_d = len(d_recs)
        n_match = min(n_g, n_d)
        for i in range(n_match):
            g_rec = g_recs[i]
            d_rec = d_recs[i]
            mr, missing_r, extra_r = _diff_relations(g_rec, d_rec, label_norm)
            mismatched_relations.extend(mr)
            missing_relations.extend(missing_r)
            extra_relations.extend(extra_r)
        # Unmatched gold copies.
        for i in range(n_match, n_g):
            # Apply reuse_index: if label is sanctioned as reused, skip.
            raw_label = g_recs[i].label
            if raw_label in reuse_index or label_norm in {
                _norm_label(k) for k in reuse_index
            }:
                continue
            missing_items.append(raw_label)
        # Unmatched direct copies (extras).
        for i in range(n_match, n_d):
            extra_items.append(d_recs[i].label)
        consumed_d_items[label_norm] = n_d

    # Direct labels not in gold at all.
    for label_norm, d_recs in d_items.items():
        if label_norm in g_items:
            continue
        # Reuse-index hint applies symmetrically: a direct external-reference
        # with a label sanctioned by reuse_index is not "extra".
        raw_labels = {r.label for r in d_recs}
        if any(rl in reuse_index for rl in raw_labels):
            continue
        for r in d_recs:
            extra_items.append(r.label)

    # ---- relations -------------------------------------------------------
    for label_norm, g_recs in g_rels.items():
        d_recs = d_rels.get(label_norm, [])
        n_g = len(g_recs)
        n_d = len(d_recs)
        n_match = min(n_g, n_d)
        for i in range(n_match):
            g_rec = g_recs[i]
            d_rec = d_recs[i]
            mr, missing_r, extra_r = _diff_relations(g_rec, d_rec, label_norm)
            mismatched_relations.extend(mr)
            missing_relations.extend(missing_r)
            extra_relations.extend(extra_r)
        for i in range(n_match, n_g):
            raw_label = g_recs[i].label
            if raw_label in reuse_index:
                continue
            missing_items.append(raw_label)
        for i in range(n_match, n_d):
            extra_items.append(d_recs[i].label)

    for label_norm, d_recs in d_rels.items():
        if label_norm in g_rels:
            continue
        raw_labels = {r.label for r in d_recs}
        if any(rl in reuse_index for rl in raw_labels):
            continue
        for r in d_recs:
            extra_items.append(r.label)

    n_diff = (
        len(missing_items)
        + len(extra_items)
        + len(mismatched_relations)
        + len(missing_relations)
        + len(extra_relations)
    )
    denom = max(1, n_gold_total)
    score = max(0.0, 1.0 - n_diff / denom)

    return SnippetDiff(
        snippet_id=snippet_id,
        missing_items=missing_items,
        extra_items=extra_items,
        mismatched_relations=mismatched_relations,
        missing_relations=missing_relations,
        extra_relations=extra_relations,
        score=score,
    )


def _diff_relations(
    g_rec,
    d_rec,
    label_norm: str,
) -> Tuple[List[Tuple[str, str, str, str]], List[Tuple[str, str]], List[Tuple[str, str]]]:
    mismatched: List[Tuple[str, str, str, str]] = []
    missing: List[Tuple[str, str]] = []
    extra: List[Tuple[str, str]] = []
    g_ex = g_rec.extra
    d_ex = d_rec.extra
    for rkey, g_val in g_ex.items():
        if rkey not in d_ex:
            missing.append((g_rec.label, rkey))
            continue
        if _norm_val(g_val) != _norm_val(d_ex[rkey]):
            mismatched.append((g_rec.label, rkey, _flatten_val(g_val), _flatten_val(d_ex[rkey])))
    for rkey in d_ex:
        if rkey not in g_ex:
            extra.append((d_rec.label, rkey))
    return mismatched, missing, extra


def _norm_val(v: Union[str, List[str]]) -> str:
    if isinstance(v, list):
        return "[" + ",".join(sorted(str(x) for x in v)) + "]"
    return str(v)


def _flatten_val(v: Union[str, List[str]]) -> str:
    if isinstance(v, list):
        return "[" + ",".join(str(x) for x in v) + "]"
    return str(v)


def diff_modules(
    gold: ModuleSummary,
    direct: ModuleSummary,
    snippet_ids: Iterable[str],
    reuse_index: Optional[Dict[str, str]] = None,
) -> Dict[str, SnippetDiff]:
    out: Dict[str, SnippetDiff] = {}
    for sid in snippet_ids:
        g_block = gold.by_snippet.get(sid) or _empty_block(sid)
        d_block = direct.by_snippet.get(sid) or _empty_block(sid)
        out[sid] = diff_snippet(g_block, d_block, reuse_index=reuse_index)
    return out


# ---------------------------------------------------------------------------
# JSON serialisation


def _diff_to_dict(d: SnippetDiff) -> dict:
    return {
        "snippet_id": d.snippet_id,
        "missing_items": list(d.missing_items),
        "extra_items": list(d.extra_items),
        "mismatched_relations": [list(t) for t in d.mismatched_relations],
        "missing_relations": [list(t) for t in d.missing_relations],
        "extra_relations": [list(t) for t in d.extra_relations],
        "score": d.score,
    }


# ---------------------------------------------------------------------------
# CLI


def _load_selection_ids(path: Path, corpus: str = "nichtlinear") -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("corpora", {}).get(corpus, [])
    return [str(e["snippet_id"]) for e in entries]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Structural per-snippet diff between two pyirk modules.")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--direct", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--snippets", type=str, help="Comma-separated snippet IDs")
    group.add_argument("--selection", type=Path, help="Path to snippet_selection.json")
    parser.add_argument("--corpus", type=str, default="nichtlinear")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    gold_src = args.gold.read_text(encoding="utf-8")
    direct_src = args.direct.read_text(encoding="utf-8")
    gold = parse_pyirk_module(gold_src)
    direct = parse_pyirk_module(direct_src)

    if args.snippets:
        sids = [s.strip() for s in args.snippets.split(",") if s.strip()]
    else:
        sids = _load_selection_ids(args.selection, corpus=args.corpus)

    diffs = diff_modules(gold, direct, sids)

    payload = {
        "snippet_ids": sids,
        "diffs": {sid: _diff_to_dict(d) for sid, d in diffs.items()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    total_score = sum(d.score for d in diffs.values()) / max(1, len(diffs))
    missing_total = sum(len(d.missing_items) + len(d.missing_relations) for d in diffs.values())
    extra_total = sum(len(d.extra_items) + len(d.extra_relations) for d in diffs.values())
    mismatched_total = sum(len(d.mismatched_relations) for d in diffs.values())
    print(
        f"STRUCTDIFF: n_snippets={len(diffs)} total_score={total_score:.4f} "
        f"missing_total={missing_total} extra_total={extra_total} "
        f"mismatched_total={mismatched_total}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
