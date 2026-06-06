"""
pyirk.nemobridge.translator — Rule classifier and .rls code generator for Nemo.

## Translation schema

All Nemo facts are read from triples.csv (3-column: subject_key, predicate_key, object_key)
as exported by nemobridge.exporter.export_datastore().

  @import triples :- csv{resource="triples.csv"} .

### Direct (R1-type) rules

Pure triple-premise rules translate to Nemo binary predicates:

  Premise body:
    - If the predicate appears as an assertion predicate of some rule:
        use derived_pred(?s, ?o)  (derived IDB predicate)
    - Otherwise:
        use triples(?s, PredKey, ?o)  (raw EDB from triples.csv)
  Head: derived_pred(?s, ?o)

Example — I64 (R3 → R83, direct mapping):
  R83(?i2, ?i1) :- triples(?i2, R3, ?i1) .

Example — I65 (R83 transitive propagation; R83 is derived by I64, so no triples() wrapper):
  R83(?i3, ?i1) :- R83(?i2, ?i1), R83(?i3, ?i2) .

Because Nemo evaluates all rules in a joint fixpoint, I64 and I65 together compute the
full transitive closure of R83 automatically.

### Transitive (R2-type) rules

Rules of the I66-type detect the pattern: premise contains both
  (rel_var, R60__is_transitive, True)   and   wildcard-relation statements.
They are translated using a standard trans/3 Datalog predicate:
  is_transitive(RelKey) .          (one fact per R60-marked relation, from generate_transitivity_facts)
  trans(?s, ?p, ?o) :- triples(?s, ?p, ?o), is_transitive(?p) .
  trans(?i1, ?r, ?i3) :- is_transitive(?r), trans(?i1, ?r, ?i2), trans(?i2, ?r, ?i3) .

### Nemo v0.10.0 note

CSV values are imported as IRIs (not string literals). Constants like R3, R83 in RLS
patterns match CSV values directly — no quoting needed.
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RuleClassification:
    rule_uri: str
    rule_short_key: str         # e.g. 'I701'
    label: str                  # R1-label of the rule
    category: str               # 'direct' | 'transitive' | 'python_only'
    rls_snippet: Optional[str]  # filled when category == 'direct'
    reason: str                 # why this category was assigned


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_all_rules(ds):
    """Return all I41__semantic_rule instances registered in ds."""
    import pyirk as p
    return p.I41["semantic rule"].get_inv_relations("R4__is_instance_of", return_subj=True)


def _filter_stms(scope):
    """Return (statements, items) for entities in *scope* via filter_relevant_stms."""
    from pyirk.ruleengine import filter_relevant_stms
    rels = scope.get_inv_relations("R20__has_defining_scope")
    return filter_relevant_stms(rels, return_items=True)


def _has_sparql_premise(rule) -> bool:
    return bool(rule.scp__premise.get_relations("R63__has_SPARQL_source", return_obj=True))


def _has_or_subscope(rule) -> bool:
    try:
        return bool(getattr(rule.scp__premise, "scp__OR", None))
    except Exception:
        return False


def _has_cheat(rule) -> bool:
    return bool(getattr(rule, "cheat", None))


def _is_literal(obj) -> bool:
    import pyirk as p
    return isinstance(obj, p.allowed_literal_types)


def _var_name(entity) -> str:
    """Return the Nemo variable notation (e.g. '?i1') for a scope-variable entity."""
    try:
        name = entity.R23__has_name_in_scope
        if name:
            return f"?{name}"
    except Exception:
        pass
    return f"?{entity.short_key}"


def _iter_assert_stms(assert_stms):
    """Yield assertion statements, skipping mode-4 auxiliary statements."""
    for stm in assert_stms:
        try:
            mode = stm.get_first_qualifier_obj_with_rel("R59__has_rule_prototype_graph_mode")
            if mode == 4:
                continue
        except Exception:
            pass
        yield stm


# ─────────────────────────────────────────────────────────────────────────────
# Derived-predicate collection (two-pass helper)
# ─────────────────────────────────────────────────────────────────────────────

def _collect_derived_predicates(rules) -> set:
    """
    First-pass scan: collect short_keys of predicates that appear as heads of
    candidate-direct rules.  These become IDB predicates in the RLS and are
    referenced directly (not via triples/3) in premise bodies of later rules.
    """
    import pyirk as p

    derived: set = set()
    for rule in rules:
        if _has_sparql_premise(rule) or _has_or_subscope(rule) or _has_cheat(rule):
            continue
        try:
            prem_stms, prem_items = _filter_stms(rule.scp__premise)
        except Exception:
            continue
        if prem_items:
            continue
        # Skip I66-type (transitive) and other non-direct patterns
        has_r60 = any(s.relation_tuple[1] == p.R60 for s in prem_stms if not _is_literal(s.relation_tuple[2]) or s.relation_tuple[1] == p.R60)
        has_wildcard = any(s.relation_tuple[1] == p.R58 for s in prem_stms)
        has_literal = any(_is_literal(s.relation_tuple[2]) for s in prem_stms)
        if has_r60 and has_wildcard:
            continue  # transitive-type
        if has_literal or has_wildcard:
            continue  # python_only
        try:
            assert_stms, assert_items = _filter_stms(rule.scp__assertion)
        except Exception:
            continue
        if assert_items:
            continue
        for stm in _iter_assert_stms(assert_stms):
            _, pred, _ = stm.relation_tuple
            if hasattr(pred, "short_key") and pred != p.R58:
                derived.add(pred.short_key)
    return derived


# ─────────────────────────────────────────────────────────────────────────────
# Single-rule classification
# ─────────────────────────────────────────────────────────────────────────────

def _classify_single_rule(rule, derived_predicates: set) -> RuleClassification:
    """Classify one rule.  derived_predicates must be pre-computed."""
    import pyirk as p

    uri = rule.uri
    key = rule.short_key
    try:
        label = str(rule.R1__has_label)
    except Exception:
        label = str(rule)

    def result(cat, snippet, reason):
        return RuleClassification(
            rule_uri=uri, rule_short_key=key, label=label,
            category=cat, rls_snippet=snippet, reason=reason,
        )

    # 1) Algorithmic / hardcoded rules
    if _has_cheat(rule):
        return result("python_only", None, "Algorithmic rule with hardcoded 'cheat' method")

    # 2) SPARQL premise
    if _has_sparql_premise(rule):
        return result("python_only", None, "SPARQL-based premise (R63__has_SPARQL_source)")

    # 3) OR subscope
    if _has_or_subscope(rule):
        return result("python_only", None, "OR-subscope in premise — branching not translatable to Datalog")

    # 4) Premise statements and Python callback anchor items
    try:
        prem_stms, prem_items = _filter_stms(rule.scp__premise)
    except Exception as e:
        return result("python_only", None, f"Error extracting premise statements: {e}")

    if prem_items:
        descs = [str(getattr(it, "R1__has_label", str(it))) for it in prem_items]
        return result("python_only", None, f"Condition-function anchor items (Python callbacks): {descs}")

    if not prem_stms:
        return result("python_only", None, "Empty premise (no pattern statements)")

    # 5) Inspect premise statements
    r60_stmts, wildcard_stmts, literal_stmts = [], [], []
    for stm in prem_stms:
        subj, pred, obj = stm.relation_tuple
        if _is_literal(obj):
            literal_stmts.append(stm)
            if pred == p.R60 and obj is True:
                r60_stmts.append(stm)
        if pred == p.R58:
            wildcard_stmts.append(stm)

    # 6) I66-type: R60 check + wildcard relation → transitive
    if r60_stmts and wildcard_stmts:
        return result(
            "transitive", None,
            "R2-type: R60__is_transitive marker + wildcard relation (R58) in premise"
            " — covered by generate_transitivity_facts()"
        )

    # 7) Other literals in premise → python_only
    if literal_stmts:
        desc = [(s.relation_tuple[1].short_key, repr(s.relation_tuple[2])) for s in literal_stmts]
        return result("python_only", None, f"Literal value(s) in premise (not triple-pattern): {desc}")

    # 8) Wildcard without R60 → python_only
    if wildcard_stmts:
        return result("python_only", None, "Wildcard relation in premise without R60__is_transitive pattern")

    # 9) Assertion scope
    try:
        assert_stms, assert_items = _filter_stms(rule.scp__assertion)
    except Exception as e:
        return result("python_only", None, f"Error extracting assertion statements: {e}")

    if assert_items:
        descs = [str(getattr(it, "R1__has_label", str(it))) for it in assert_items]
        return result("python_only", None, f"Assertion creates new entities (fiat prototypes): {descs}")

    # 10) Generate RLS snippet
    try:
        snippet = _build_direct_snippet(rule, prem_stms, list(_iter_assert_stms(assert_stms)),
                                        derived_predicates)
        return result("direct", snippet, "Pure triple-pattern premise and assertion — translatable to Datalog")
    except Exception as e:
        return result("python_only", None, f"RLS snippet generation failed: {e}")


def _build_direct_snippet(rule, prem_stms, assert_stms_filtered, derived_predicates: set) -> str:
    """Build the Datalog rule lines for one direct rule."""
    # Body from premise statements
    body_parts = []
    for stm in prem_stms:
        subj, pred, obj = stm.relation_tuple
        s_var = _var_name(subj)
        p_key = pred.short_key
        o_var = _var_name(obj)
        if p_key in derived_predicates:
            body_parts.append(f"{p_key}({s_var}, {o_var})")
        else:
            body_parts.append(f"triples({s_var}, {p_key}, {o_var})")

    if not body_parts:
        raise ValueError(f"Rule {rule.short_key} has no premise statements to translate")

    body = ", ".join(body_parts)

    # Head from assertion statements
    head_lines = []
    for stm in assert_stms_filtered:
        subj, pred, obj = stm.relation_tuple
        s_var = _var_name(subj)
        p_key = pred.short_key
        o_var = _var_name(obj)
        head_lines.append(f"{p_key}({s_var}, {o_var}) :- {body} .")

    if not head_lines:
        raise ValueError(f"Rule {rule.short_key} produced no assertion head lines")

    try:
        label = str(rule.R1__has_label)
    except Exception:
        label = rule.short_key

    return "\n".join([f"% {rule.short_key}: {label}"] + head_lines)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def classify_rules(ds) -> list:
    """Classify all semantic rules in *ds*.

    Returns a list of RuleClassification instances (one per rule).
    Uses a two-pass approach: first collects derived predicate keys, then
    classifies each rule using that context.

    Categories:
      'direct'      — pure triple-pattern premise/assertion; rls_snippet filled.
      'transitive'  — I66-type with R60__is_transitive; covered by generate_transitivity_facts.
      'python_only' — requires Python callbacks, SPARQL, OR-scopes, or fiat items.
    """
    rules = _get_all_rules(ds)
    derived = _collect_derived_predicates(rules)
    logger.debug("Derived predicates: %s", derived)
    return [_classify_single_rule(rule, derived) for rule in rules]


def generate_transitivity_facts(ds) -> str:
    """Return a .rls snippet with is_transitive(RelKey) facts for all R60-transitive relations.

    Iterates all relations in ds.relations and emits one Datalog fact per relation
    with R60__is_transitive == True:
        is_transitive(RelKey) .

    Nemo v0.10.0: constants in facts are IRIs (no quotes), consistent with CSV imports.
    """
    lines = ["% is_transitive facts — auto-generated from R60__is_transitive=True"]
    count = 0
    for rel_uri, rel in sorted(ds.relations.items()):
        try:
            val = rel.R60__is_transitive
        except Exception:
            val = None
        if val:
            lines.append(f"is_transitive({rel.short_key}) .")
            count += 1
    if count == 0:
        lines.append("% (no transitive relations found)")
    return "\n".join(lines)


_TRANS_BODY = """\
% Transitive closure — standard Datalog pattern for R2-type rules
% Base: include all triples whose predicate is marked as transitive
trans(?s, ?p, ?o) :- triples(?s, ?p, ?o), is_transitive(?p) .
% Recursive step: apply transitivity until fixpoint
trans(?i1, ?r, ?i3) :- is_transitive(?r), trans(?i1, ?r, ?i2), trans(?i2, ?r, ?i3) ."""


def generate_rls(ds, *, include_transitivity: bool = True) -> str:
    """Compile all direct and transitive rules into a single Nemo .rls text.

    Structure:
      @import triples (once)
      Direct rule bodies (Datalog rules derived from classify_rules)
      Transitivity facts + trans/3 recursion (if include_transitivity=True and any R2-rules exist)
      @export directives for all derived head predicates and trans

    Returns the complete .rls string ready to write to a file.
    """
    classifications = classify_rules(ds)

    direct_clfs = [c for c in classifications if c.category == "direct"]
    has_transitive = any(c.category == "transitive" for c in classifications)

    # Collect head predicates for @export
    head_preds: set = set()
    for clf in direct_clfs:
        if clf.rls_snippet:
            for line in clf.rls_snippet.splitlines():
                line = line.strip()
                if line and not line.startswith("%") and ":-" in line:
                    head = line.split(":-")[0].strip()
                    pred = head.split("(")[0].strip()
                    if pred:
                        head_preds.add(pred)

    out = []
    out.append("% nemobridge auto-generated rules — do not edit manually")
    out.append("")
    out.append('@import triples :- csv{resource="triples.csv"} .')

    if direct_clfs:
        out.append("")
        out.append("% ── Direct rules ─────────────────────────────────────────")
        for clf in direct_clfs:
            out.append("")
            out.append(clf.rls_snippet)

    if include_transitivity and has_transitive:
        out.append("")
        out.append("% ── Transitivity ─────────────────────────────────────────")
        out.append("")
        out.append(generate_transitivity_facts(ds))
        out.append("")
        out.append(_TRANS_BODY)

    if head_preds or (include_transitivity and has_transitive):
        out.append("")
        out.append("% ── Exports ──────────────────────────────────────────────")
        for pred in sorted(head_preds):
            out.append(f'@export {pred} :- csv{{resource="output_{pred}.csv"}} .')
        if include_transitivity and has_transitive:
            out.append('@export trans :- csv{resource="output_trans.csv"} .')

    return "\n".join(out)


def classification_to_json(items: list) -> str:
    """Serialize a list of RuleClassification to a JSON string."""
    return json.dumps([asdict(item) for item in items], indent=2, ensure_ascii=False)
