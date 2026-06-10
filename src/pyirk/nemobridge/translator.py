"""
pyirk.nemobridge.translator — Rule classifier and .rls code generator for Nemo.

## Translation schema (Phase 2.1: ternary ``fact``-model with full URIs)

The EDB is ``triples.csv`` whose cells carry FULL entity URIs as strings
(e.g. ``"irk:/builtins#R3"``); the exporter writes them that way (Gate-1 fix).
Every ``@import`` MUST declare ``format=(string, ...)`` — otherwise an unquoted
CSV cell does not unify with a ``"..."`` constant in a rule head and the join
silently fails (transitive closure does not fire).

All derived knowledge is represented by ONE ternary IDB predicate ``fact/3``;
predicates are NEVER Nemo predicate names but always full-URI data terms.

  @import triples :- csv{resource="triples.csv", format=(string,string,string)} .
  fact(?s, ?p, ?o) :- triples(?s, ?p, ?o) .

### Direct (R1-type) rules

Pure triple-premise rules translate to ternary ``fact`` rules. The premise
predicate(s) and the assertion predicate appear as URI-string constants:

  fact(?s, "irk:/builtins#R83", ?o) :- fact(?s, "irk:/builtins#R3", ?o) .

### Transitive (R2-type) rules

  is_transitive("irk:/builtins#R17") .          (one fact per R60-marked relation)
  fact(?s, ?p, ?o) :- is_transitive(?p), fact(?s, ?p, ?x), fact(?x, ?p, ?o) .

### Export

A single ``@export fact :- csv{resource="output_fact.csv"} .`` directive.
Mapping (see ``delegation._materialize_tuples``) resolves all three columns
via ``ds.get_entity_by_uri`` — no short_key path.
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
# Single-rule classification
# ─────────────────────────────────────────────────────────────────────────────

def _classify_single_rule(rule) -> RuleClassification:
    """Classify one rule using the ternary ``fact``-model."""
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
        snippet = _build_direct_snippet(rule, prem_stms, list(_iter_assert_stms(assert_stms)))
        return result("direct", snippet, "Pure triple-pattern premise and assertion — translatable to Datalog")
    except Exception as e:
        return result("python_only", None, f"RLS snippet generation failed: {e}")


def _build_direct_snippet(rule, prem_stms, assert_stms_filtered) -> str:
    """Build ternary ``fact``-rule lines for one direct rule.

    Every premise/assertion triple becomes a ``fact(?s, "<pred-uri>", ?o)``
    pattern; the predicate URI appears as a quoted string constant, never as
    a Nemo predicate name. No derived-predicate handling needed: all rules
    target the single ``fact`` IDB, the joint fixpoint handles propagation.
    """
    body_parts = []
    for stm in prem_stms:
        subj, pred, obj = stm.relation_tuple
        s_var = _var_name(subj)
        o_var = _var_name(obj)
        body_parts.append(f'fact({s_var}, "{pred.uri}", {o_var})')

    if not body_parts:
        raise ValueError(f"Rule {rule.short_key} has no premise statements to translate")

    body = ", ".join(body_parts)

    head_lines = []
    for stm in assert_stms_filtered:
        subj, pred, obj = stm.relation_tuple
        s_var = _var_name(subj)
        o_var = _var_name(obj)
        head_lines.append(f'fact({s_var}, "{pred.uri}", {o_var}) :- {body} .')

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

    Categories:
      'direct'      — pure triple-pattern premise/assertion; rls_snippet filled.
      'transitive'  — I66-type with R60__is_transitive; covered by generate_transitivity_facts.
      'python_only' — requires Python callbacks, SPARQL, OR-scopes, or fiat items.
    """
    rules = _get_all_rules(ds)
    return [_classify_single_rule(rule) for rule in rules]


def generate_transitivity_facts(ds) -> str:
    """Return a ``.rls`` snippet of ``is_transitive("<rel-uri>")`` facts.

    One quoted-URI string per relation with R60__is_transitive=True. The
    quoting is mandatory: ``fact``'s predicate column carries quoted URI
    strings (format=(string,...)) and a join only unifies when both sides
    are string-typed.
    """
    lines = ["% is_transitive facts — auto-generated from R60__is_transitive=True"]
    count = 0
    for rel_uri, rel in sorted(ds.relations.items()):
        try:
            val = rel.R60__is_transitive
        except Exception:
            val = None
        if val:
            lines.append(f'is_transitive("{rel.uri}") .')
            count += 1
    if count == 0:
        lines.append("% (no transitive relations found)")
    return "\n".join(lines)


_TRANS_BODY = """\
% Transitive closure — standard Datalog pattern for R2-type rules
fact(?s, ?p, ?o) :- is_transitive(?p), fact(?s, ?p, ?x), fact(?x, ?p, ?o) ."""


def generate_rls(ds, *, include_transitivity: bool = True) -> str:
    """Compile all direct and transitive rules into a single Nemo ``.rls`` text.

    Structure:
      ``@import triples :- csv{resource="triples.csv", format=(string,string,string)} .``
      ``fact(?s, ?p, ?o) :- triples(?s, ?p, ?o) .``       (seed the IDB)
      Direct rules (ternary ``fact``-form, URI-string constants)
      Transitivity facts + ternary recursion (if ``include_transitivity``)
      ``@export fact :- csv{resource="output_fact.csv"} .``
    """
    classifications = classify_rules(ds)

    direct_clfs = [c for c in classifications if c.category == "direct"]
    has_transitive = any(c.category == "transitive" for c in classifications)

    out = []
    out.append("% nemobridge auto-generated rules — do not edit manually")
    out.append("")
    out.append('@import triples :- csv{resource="triples.csv", format=(string,string,string)} .')
    out.append("")
    out.append("% Seed the ternary fact IDB from the EDB triples")
    out.append("fact(?s, ?p, ?o) :- triples(?s, ?p, ?o) .")

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

    out.append("")
    out.append("% ── Exports ──────────────────────────────────────────────")
    out.append('@export fact :- csv{resource="output_fact.csv"} .')

    return "\n".join(out)


def classification_to_json(items: list) -> str:
    """Serialize a list of RuleClassification to a JSON string."""
    return json.dumps([asdict(item) for item in items], indent=2, ensure_ascii=False)
