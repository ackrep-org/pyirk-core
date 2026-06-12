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


def _is_scope_internal(entity) -> bool:
    """Mirror of :func:`exporter.is_scope_internal` — kept inline to avoid an
    exporter→translator coupling cycle."""
    try:
        return bool(entity.get_relations("R20__has_defining_scope"))
    except Exception:
        return False


def _obj_term(obj) -> str:
    """Render a premise/assertion object as a Nemo term.

    Three branches:
      * Literal (bool/int/float/str/…) → quoted ``LIT:<repr>`` string constant,
        matching the encoding used by :func:`exporter.encode_literal`. This is
        what lets a literal premise pattern unify with rows in
        ``literal_triples.csv`` (H5 Extension Phase 1).
      * Scope-internal entity (variable of THIS rule's setting scope) →
        ``?<name>`` variable reference via :func:`_var_name`.
      * Real external entity (e.g. ``zb.I7435["human"]``) → quoted full-URI
        constant. Pre-Phase-1 the translator emitted these as variables too
        (``?I7435``), which left a free head-variable in some snippets — a
        latent bug that surfaces as soon as those rules are actually evaluated
        by Nemo (e.g. on the Zebra dataset, where I763/I796 hit it).
    """
    from .exporter import encode_literal
    if _is_literal(obj):
        return f'"{encode_literal(obj)}"'
    if _is_scope_internal(obj):
        return _var_name(obj)
    return f'"{obj.uri}"'


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

    # 7) Other literals in premise → handled by literal-fact pattern (Phase 1 H5
    # Extension). The literal value enters the ternary fact() body as a quoted
    # ``LIT:<repr>`` constant; the exporter writes those rows into
    # ``literal_triples.csv`` and the @import in ``generate_rls`` makes them
    # match. This branch deliberately does NOT return — the rule continues
    # through the assertion-scope checks and snippet generation below.

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


def _collect_scope_vars(prem_stms) -> list:
    """Return scope-internal variable terms used in *prem_stms*, sorted.

    Used to add pairwise inequality constraints so the Datalog rule matches
    the native engine's subgraph-MONOMORPHISM semantics — distinct rule
    variables must bind to distinct data nodes. Without this, Datalog would
    over-derive (e.g. I705 produces (p, R50, p) self-loops because Datalog
    happily matches ``p1 = p2`` when no equality forbids it).
    """
    seen = []
    seen_set = set()
    for stm in prem_stms:
        subj, _pred, obj = stm.relation_tuple
        for e in (subj, obj):
            if not _is_scope_internal(e):
                continue
            term = _var_name(e)
            if term not in seen_set:
                seen_set.add(term)
                seen.append(term)
    return sorted(seen)


def _build_direct_snippet(rule, prem_stms, assert_stms_filtered) -> str:
    """Build ternary ``fact``-rule lines for one direct rule.

    Every premise/assertion triple becomes a ``fact(?s, "<pred-uri>", ?o)``
    pattern; the predicate URI appears as a quoted string constant, never as
    a Nemo predicate name. Literal objects become quoted ``LIT:<repr>``
    constants — matched against the literal-fact rows the exporter writes
    into ``literal_triples.csv`` (Phase 1 H5 Extension). No derived-predicate
    handling needed: all rules target the single ``fact`` IDB, the joint
    fixpoint handles propagation.

    The body is augmented with pairwise ``?x != ?y`` constraints between the
    scope-internal variables; see :func:`_collect_scope_vars` for the why.
    """
    body_parts = []
    for stm in prem_stms:
        subj, pred, obj = stm.relation_tuple
        if _is_literal(subj):
            raise ValueError(
                f"Rule {rule.short_key}: literal value at subject position"
                " is not translatable to Datalog"
            )
        s_term = _obj_term(subj)
        o_term = _obj_term(obj)
        body_parts.append(f'fact({s_term}, "{pred.uri}", {o_term})')

    if not body_parts:
        raise ValueError(f"Rule {rule.short_key} has no premise statements to translate")

    scope_vars = _collect_scope_vars(prem_stms)
    for i, vi in enumerate(scope_vars):
        for vj in scope_vars[i + 1:]:
            body_parts.append(f"{vi} != {vj}")

    body = ", ".join(body_parts)

    head_lines = []
    for stm in assert_stms_filtered:
        subj, pred, obj = stm.relation_tuple
        if _is_literal(subj):
            raise ValueError(
                f"Rule {rule.short_key}: literal value at assertion subject position"
                " is not translatable to Datalog"
            )
        s_term = _obj_term(subj)
        o_term = _obj_term(obj)
        head_lines.append(f'fact({s_term}, "{pred.uri}", {o_term}) :- {body} .')

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


def generate_rls(ds, *, include_transitivity: bool = True, restrict_to=None) -> str:
    """Compile direct and transitive rules into a single Nemo ``.rls`` text.

    Structure:
      ``@import triples :- csv{resource="triples.csv", format=(string,string,string)} .``
      ``@import literal_triples :- csv{resource="literal_triples.csv", ...} .``
      ``fact(?s, ?p, ?o) :- triples(?s, ?p, ?o) .``       (seed the IDB)
      ``fact(?s, ?p, ?o) :- literal_triples(?s, ?p, ?o) .``
      Direct rules (ternary ``fact``-form, URI-string constants)
      Transitivity facts + ternary recursion (if ``include_transitivity`` AND
      at least one rule in ``restrict_to`` is classified as transitive)
      ``@export fact :- csv{resource="output_fact.csv"} .``

    Parameters
    ----------
    restrict_to : Optional[Iterable[str]]
        If given, only emit snippets for rules whose ``short_key`` is in
        this set. ``None`` (default) keeps the prior behaviour and includes
        every direct/transitive rule found in ``ds`` — relied upon by the
        Phase-2 OCSE workload where all rules are requested at once. The
        single-rule delegation path (e.g. ``apply_semantic_rules(I800)``)
        sets this to the requested rule keys so Nemo does not over-derive
        from rules the caller did not ask for. Mixed mode possible.
    """
    classifications = classify_rules(ds)

    if restrict_to is not None:
        restrict_keys = set(restrict_to)
        classifications = [c for c in classifications if c.rule_short_key in restrict_keys]

    direct_clfs = [c for c in classifications if c.category == "direct"]
    has_transitive = any(c.category == "transitive" for c in classifications)

    out = []
    out.append("% nemobridge auto-generated rules — do not edit manually")
    out.append("")
    out.append('@import triples :- csv{resource="triples.csv", format=(string,string,string)} .')
    out.append(
        '@import literal_triples :- '
        'csv{resource="literal_triples.csv", format=(string,string,string)} .'
    )
    out.append("")
    out.append("% Seed the ternary fact IDB from the EDB triples (entity + literal facts)")
    out.append("fact(?s, ?p, ?o) :- triples(?s, ?p, ?o) .")
    out.append("fact(?s, ?p, ?o) :- literal_triples(?s, ?p, ?o) .")

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
