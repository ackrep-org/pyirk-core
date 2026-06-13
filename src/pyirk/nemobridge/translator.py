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


# Curated SPARQL-premise rules that must NOT be delegated, even when their
# algebra would technically pass the pure-BGP / BGP+!= check. The native
# engine is the reference oracle, and either it has no well-defined
# semantics on the zebra-only KB (I725), or the Nemo EDB by design does not
# carry the facts the rule binds against (I803).
#
#   * I725 — native crashes with ``AssertionError`` in
#     ``ruleengine.py::_process_result_map`` (object positions bind to
#     literals — see ``experiments/h5_sparql/recon.md`` §"I725 — Native
#     Verhalten").
#
#   * I803 — premise binds ``?tuple :R39 ?itm2`` (R39__has_element on the
#     main R51-tuple). pyirk's ``new_tuple`` always attaches a
#     ``has_index`` qualifier to that statement, so the exporter routes it
#     to ``stmts.csv`` + ``quals_R40.csv``; only the (unqualified)
#     reification-anchor R39 statements end up in ``triples.csv``. The
#     Nemo EDB seed (``fact(?s,?p,?o) :- triples(?s,?p,?o)``) therefore
#     never produces a fact where the main tuple is the R39 subject, and
#     the SPARQL-BGP+!= translation fires zero times under delegation
#     while native yields ~88 derivations on zebra02. Honest-Stop:
#     classified ``python_only`` until the EDB seed admits qualified
#     entity-entity statements (cross-cutting H5-extension concern, not a
#     Stage-4 fix).
_SPARQL_PYTHON_ONLY_RULE_KEYS = {"I725", "I803"}

# Per-key python_only reason for the curated SPARQL-premise rules above.
# Keys not listed here fall back to the generic "rule excluded by curation"
# string in :func:`_classify_single_rule`.
_SPARQL_PYTHON_ONLY_REASONS = {
    "I725": (
        "SPARQL: rule excluded by curation"
        " (native undefined on zebra KB — AssertionError in ruleengine)"
    ),
    "I803": (
        "SPARQL: rule excluded by curation"
        " (BGP binds qualified-only R39 facts which the Nemo EDB seed does"
        " not carry; native ≠ delegated multiset)"
    ),
}


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


def _pred_term(stm) -> str:
    """Render a statement's predicate as a Nemo term.

    Two branches:
      * Wildcard rel-var statement (``pred == R58`` with an ``R34__has_proxy_item``
        qualifier pointing at a scope-internal ``I40["general relation"]``
        instance) → ``?<name>`` variable reference. This is how
        ``ConditionManager.new_rel`` encodes a rel-var as the predicate of a
        conclusion (see :func:`pyirk.builtin_entities.new_rel`): the visible
        statement carries ``R58`` and the rel-var lives in a qualifier.
      * Otherwise → quoted full-URI string constant, matching the column
        encoding used by the EDB CSVs.
    """
    import pyirk as p
    pred = stm.predicate
    if pred == p.R58:
        proxy = stm.get_first_qualifier_obj_with_rel(
            "R34__has_proxy_item", tolerate_key_error=True,
        )
        if proxy is not None and _is_scope_internal(proxy):
            return _var_name(proxy)
    return f'"{pred.uri}"'


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
# SPARQL premise translation (H5 SPARQL Stage 1: pure BGP)
# ─────────────────────────────────────────────────────────────────────────────
#
# The SPARQL premise of a rule (``R63__has_SPARQL_source``) is translated to a
# conjunction of ``fact(...)`` atoms — same ternary model as the existing
# triple-pattern rules — but ONLY for the strictly translatable fragment:
#
#   * Algebra contains ONLY a ``BGP`` node (possibly wrapped in
#     ``Project``/``SelectQuery``/``Slice``/``Distinct``/``Reduced``/
#     ``OrderBy``/``ToList``).
#   * NO ``Filter`` (incl. ``!=``), ``Minus``, ``Union``, ``LeftJoin``
#     (OPTIONAL), ``Extend`` (BIND), ``Group``/``AggregateJoin``, property
#     paths, or any other unknown construct.
#
# Detection runs on the *rdflib SPARQL algebra* (``parseQuery`` +
# ``translateQuery``); we deliberately do NOT regex the query source — that is
# the recon script's job. Stages 2 / 4 / 5 (inequality, negation) extend the
# accepted fragment; until then anything richer than pure BGP stays
# ``python_only``.


def _build_sparql_query_text(rule) -> str:
    """Build the same prefixed SPARQL string the native engine wraps the
    ``R63__has_SPARQL_source`` body with — :meth:`apply_sparql_premise`
    prepends ``PREFIX`` lines and a ``SELECT`` clause before the user's
    ``WHERE``-block. The actual projection list is irrelevant for algebra
    classification (it only affects how the result is shaped); we pick the
    setting-scope variables so the SELECT clause stays well-formed.
    """
    import textwrap
    import pyirk as p

    sparql_src = rule.scp__premise.get_relations(
        "R63__has_SPARQL_source", return_obj=True,
    )
    where_clause = textwrap.dedent(sparql_src[0])

    prefixes = []
    for mod_uri, prefix in p.ds.uri_prefix_mapping.a.items():
        if mod_uri == p.settings.BUILTINS_URI:
            prefix = ""
        prefixes.append(f"PREFIX {prefix}: <{mod_uri}#>")
    prefix_block = "\n".join(prefixes)

    setting = rule.scp__setting
    items = setting.get_inv_relations("R20__has_defining_scope", return_subj=True)
    names = []
    seen = set()
    for it in items:
        lbl = getattr(it, "R23__has_name_in_scope", None)
        if not isinstance(lbl, str):
            continue
        if lbl.startswith("?"):
            lbl = lbl[1:]
        if " " in lbl or not lbl:
            continue
        if lbl in seen:
            continue
        seen.add(lbl)
        names.append(lbl)
    select_clause = "SELECT " + " ".join("?" + v for v in names) if names else "SELECT *"

    return f"{prefix_block}\n{select_clause}\n{where_clause}"


def _sparql_extract_pure_bgp(rule):
    """Parse the rule's SPARQL premise and return the BGP triple list iff
    the algebra is a pure BGP (no Filter/Minus/Union/etc.). Otherwise
    return ``None``.

    Detection is purely structural on the rdflib algebra tree — no string
    matching on the SPARQL source.
    """
    from rdflib.plugins.sparql.parser import parseQuery
    from rdflib.plugins.sparql.algebra import translateQuery
    from rdflib.plugins.sparql.parserutils import CompValue
    from rdflib.paths import Path

    qtext = _build_sparql_query_text(rule)
    parsed = parseQuery(qtext)
    algebra = translateQuery(parsed)

    bgp_triples = []
    rejected_reason = []

    def _walk(node):
        if not isinstance(node, CompValue):
            return
        name = node.name
        if name in ("BGP", "Bgp"):
            for triple in node.triples:
                bgp_triples.append(triple)
        elif name in (
            "SelectQuery", "Project", "Slice", "Distinct", "Reduced",
            "OrderBy", "ToList",
        ):
            _walk(node.p)
        elif name == "Filter":
            # Filter is a "soft" rejection — Stage 4 supports ``!=``. Recurse
            # into the subpattern so harder rejections inside (Minus, Union,
            # …) get detected too; the post-walk step drops "Filter" when a
            # harder reason is present, so I741 reports ``Minus`` rather than
            # the ``Filter`` that happens to wrap it.
            rejected_reason.append("Filter")
            _walk(node.p)
        elif name == "Minus":
            rejected_reason.append("Minus")
        elif name == "Union":
            rejected_reason.append("Union")
        elif name == "LeftJoin":
            rejected_reason.append("LeftJoin/OPTIONAL")
        elif name == "Extend":
            rejected_reason.append("Extend/BIND")
        elif name in ("Group", "AggregateJoin"):
            rejected_reason.append("Group/Aggregation")
        elif name == "Join":
            _walk(node.p1)
            _walk(node.p2)
        else:
            rejected_reason.append(f"unsupported construct: {name}")

    _walk(algebra.algebra)

    if rejected_reason:
        reasons = sorted(set(rejected_reason))
        if len(reasons) > 1 and "Filter" in reasons:
            reasons = [r for r in reasons if r != "Filter"]
        return None, "; ".join(reasons)

    if not bgp_triples:
        return None, "no BGP triples found"

    # property-path predicate (e.g. ``foaf:knows+``) — reject
    for s, pp, o in bgp_triples:
        if isinstance(pp, Path):
            return None, "property-path predicate in BGP"
        if isinstance(pp, CompValue):
            return None, "non-simple predicate in BGP"

    return bgp_triples, None


def _sparql_extract_bgp_with_inequality(rule):
    """Parse the rule's SPARQL premise and return ``(triples, ineq_pairs)``
    iff the algebra is a BGP wrapped in a single ``Filter`` whose expression
    is a (possibly AND-conjoined) collection of ``?var_a != ?var_b`` atoms
    between TWO VARIABLES. Otherwise return ``None``.

    Accepted shape (H5 SPARQL Stage 4):

        Project/SelectQuery/Slice/... -> Filter(expr, BGP(triples))

    where ``expr`` is either

      * a single ``RelationalExpression(?a != ?b)``, OR
      * a ``ConditionalAndExpression`` whose every atom is such an inequality.

    Anything else (constants, equality, ordering, OR, NOT, function calls,
    Minus/Union below the Filter) → ``None``. Honest-stop: the classifier
    then falls through to ``python_only`` with the existing ``(Filter)``
    rejection reason — no silent semantic drift.
    """
    from rdflib.plugins.sparql.parser import parseQuery
    from rdflib.plugins.sparql.algebra import translateQuery
    from rdflib.plugins.sparql.parserutils import CompValue
    from rdflib.paths import Path
    from rdflib.term import Variable

    qtext = _build_sparql_query_text(rule)
    parsed = parseQuery(qtext)
    algebra = translateQuery(parsed)

    node = algebra.algebra
    while isinstance(node, CompValue) and node.name in (
        "SelectQuery", "Project", "Slice", "Distinct", "Reduced",
        "OrderBy", "ToList",
    ):
        node = node.p

    if not isinstance(node, CompValue) or node.name != "Filter":
        return None

    bgp_node = node.p
    if not isinstance(bgp_node, CompValue) or bgp_node.name not in ("BGP", "Bgp"):
        return None

    bgp_triples = list(bgp_node.triples)
    for s, pp, o in bgp_triples:
        if isinstance(pp, Path):
            return None
        if isinstance(pp, CompValue):
            return None

    def _flatten_and(expr):
        """Return list of atoms iff *expr* is a (possibly nested) AND of
        atoms, else ``None`` to signal honest-stop."""
        if not isinstance(expr, CompValue):
            return None
        if expr.name == "RelationalExpression":
            return [expr]
        if expr.name == "ConditionalAndExpression":
            atoms = []
            head = _flatten_and(expr.expr)
            if head is None:
                return None
            atoms.extend(head)
            for sub in (expr.other or []):
                tail = _flatten_and(sub)
                if tail is None:
                    return None
                atoms.extend(tail)
            return atoms
        return None

    atoms = _flatten_and(node.expr)
    if atoms is None:
        return None

    ineq_pairs = []
    for atom in atoms:
        if atom.name != "RelationalExpression":
            return None
        if atom.op != "!=":
            return None
        a, b = atom.expr, atom.other
        if not isinstance(a, Variable) or not isinstance(b, Variable):
            return None
        ineq_pairs.append((a, b))

    if not bgp_triples:
        return None

    return bgp_triples, ineq_pairs


def _sparql_bgp_term(term) -> str:
    """Render an rdflib BGP term as a Nemo term.

    Three branches mirroring :func:`_obj_term`:
      * ``Variable('p2')`` → ``?p2`` — same naming convention the conclusion
        side uses for scope-internal entities via :func:`_var_name`, so the
        variable ``p2`` introduced in the SPARQL premise binds to the same
        position the assertion ``cm.new_rel(cm.p2, ..., ...)`` projects to.
      * ``URIRef('irk:/.../R50')`` → ``"irk:/.../R50"`` — quoted full URI,
        matching how the EDB CSV columns are encoded.
      * ``Literal('true', xsd:boolean)`` → ``"LIT:True"`` — uses
        ``encode_literal(literal.toPython())`` so the encoding is BIT-exact
        to :func:`exporter.encode_literal`, which is what
        ``literal_triples.csv`` rows carry. Mixing a hand-rolled encoding
        here would silently produce non-matching tokens; reusing the
        exporter's helper is the only correctness guarantee.
    """
    from rdflib.term import Variable, URIRef, Literal
    from .exporter import encode_literal

    if isinstance(term, Variable):
        return f"?{str(term)}"
    if isinstance(term, URIRef):
        return f'"{str(term)}"'
    if isinstance(term, Literal):
        return f'"{encode_literal(term.toPython())}"'
    raise ValueError(
        f"unsupported rdflib BGP term {term!r} (type {type(term).__name__})"
    )


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

    # 2) SPARQL premise — try the pure-BGP branch first (H5 SPARQL Stage 1);
    # anything richer than pure BGP stays ``python_only`` for now (Stages 2/4/5
    # extend the accepted fragment).
    if _has_sparql_premise(rule):
        if key in _SPARQL_PYTHON_ONLY_RULE_KEYS:
            return result(
                "python_only", None,
                _SPARQL_PYTHON_ONLY_REASONS.get(
                    key,
                    "SPARQL: rule excluded by curation",
                ),
            )
        try:
            bgp_triples, rejection = _sparql_extract_pure_bgp(rule)
        except Exception as ex:
            return result(
                "python_only", None,
                f"SPARQL-based premise: algebra parse failed ({type(ex).__name__}: {ex})"
            )

        # Stage 4: BGP + ``FILTER(?a != ?b [&& ...])``. Tried after the pure-BGP
        # check and BEFORE the ``python_only (Filter)`` fallthrough, so any
        # filter form richer than a conjunction of two-variable inequalities
        # (constants, equality, OR, NOT, function calls, …) falls through to
        # the existing ``(Filter)`` reason without semantic drift.
        ineq_pairs = None
        if bgp_triples is None and rejection == "Filter":
            try:
                extracted = _sparql_extract_bgp_with_inequality(rule)
            except Exception as ex:
                return result(
                    "python_only", None,
                    f"SPARQL-based premise: inequality algebra parse failed"
                    f" ({type(ex).__name__}: {ex})"
                )
            if extracted is not None:
                bgp_triples, ineq_pairs = extracted

        if bgp_triples is None:
            return result(
                "python_only", None,
                f"SPARQL-based premise: not a pure BGP ({rejection})"
            )

        # The assertion uses the SAME scope-internal variable names as the
        # SPARQL premise (rule authors declare them in the setting scope via
        # ``new_var`` / ``new_rel_var`` and reference them in both places).
        # The conclusion side is handled by the existing assertion-snippet
        # path; only the premise body is replaced with the BGP-derived atoms.
        try:
            assert_stms, assert_items = _filter_stms(rule.scp__assertion)
        except Exception as ex:
            return result(
                "python_only", None,
                f"SPARQL premise: assertion-stmts extraction failed ({ex})"
            )

        if assert_items:
            descs = [str(getattr(it, "R1__has_label", str(it))) for it in assert_items]
            return result(
                "python_only", None,
                f"SPARQL premise: assertion creates new entities (fiat prototypes): {descs}"
            )

        try:
            snippet = _build_sparql_bgp_snippet(
                rule, bgp_triples, list(_iter_assert_stms(assert_stms)),
                ineq_pairs=ineq_pairs,
            )
            if ineq_pairs:
                reason = (
                    "SPARQL premise: BGP + inequality — translated to Datalog"
                    " (H5 SPARQL Stage 4)"
                )
            else:
                reason = (
                    "SPARQL premise: pure BGP — translated to Datalog"
                    " (H5 SPARQL Stage 1)"
                )
            return result("direct", snippet, reason)
        except Exception as ex:
            return result(
                "python_only", None,
                f"SPARQL premise: BGP snippet generation failed ({type(ex).__name__}: {ex})"
            )

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
        p_term = _pred_term(stm)
        o_term = _obj_term(obj)
        body_parts.append(f'fact({s_term}, {p_term}, {o_term})')

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
        p_term = _pred_term(stm)
        o_term = _obj_term(obj)
        head_lines.append(f'fact({s_term}, {p_term}, {o_term}) :- {body} .')

    if not head_lines:
        raise ValueError(f"Rule {rule.short_key} produced no assertion head lines")

    try:
        label = str(rule.R1__has_label)
    except Exception:
        label = rule.short_key

    return "\n".join([f"% {rule.short_key}: {label}"] + head_lines)


def _build_sparql_bgp_snippet(rule, bgp_triples, assert_stms_filtered, ineq_pairs=None) -> str:
    """Build ternary ``fact``-rule lines for one SPARQL-premise rule whose
    premise is a BGP (H5 SPARQL Stage 1) optionally augmented with a
    conjunction of ``?a != ?b`` inequality constraints (H5 SPARQL Stage 4).

    Each BGP triple ``(s, p, o)`` becomes a ``fact(<s>, <p>, <o>)`` atom; the
    assertion statements are rendered the same way the GRAPH-premise direct
    snippet does (so a rel-var conclusion routed through ``R58`` + ``R34``
    qualifier comes out as ``?<rel-var-name>`` via :func:`_pred_term`).

    The SPARQL variable names line up with the scope-internal variable names
    by construction: the rule author declares the variables in the setting
    scope (``new_var(p1=...)`` / ``new_rel_var("rel1")``), which fixes their
    ``R23__has_name_in_scope``; the same names then appear in the SPARQL
    source. The Nemo body uses ``?<name>`` directly from the rdflib
    ``Variable`` term; the conclusion uses ``?<name>`` from
    :func:`_var_name`; both agree.

    When *ineq_pairs* is given, each ``(a, b)`` rdflib ``Variable`` pair
    becomes a Nemo ``?a != ?b`` body atom — same mechanic as the
    monomorphism-default constraints in :func:`_build_direct_snippet`.
    Set-dedup over ``frozenset({a, b})`` prevents the SPARQL ``FILTER`` from
    re-emitting a pair that is already present via the (currently unused
    here) default monomorphism path.
    """
    body_parts = []
    for triple in bgp_triples:
        s, pp, o = triple
        body_parts.append(
            f'fact({_sparql_bgp_term(s)}, {_sparql_bgp_term(pp)}, {_sparql_bgp_term(o)})'
        )

    if not body_parts:
        raise ValueError(
            f"Rule {rule.short_key}: BGP yielded no atoms — premise is empty"
        )

    if ineq_pairs:
        seen_pairs = set()
        for a, b in ineq_pairs:
            a_term = f"?{str(a)}"
            b_term = f"?{str(b)}"
            if a_term == b_term:
                continue
            key = frozenset({a_term, b_term})
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            body_parts.append(f"{a_term} != {b_term}")

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
        p_term = _pred_term(stm)
        o_term = _obj_term(obj)
        head_lines.append(f'fact({s_term}, {p_term}, {o_term}) :- {body} .')

    if not head_lines:
        raise ValueError(
            f"Rule {rule.short_key}: SPARQL premise produced no assertion head lines"
        )

    try:
        label = str(rule.R1__has_label)
    except Exception:
        label = rule.short_key

    tag = "SPARQL-BGP+!=" if ineq_pairs else "SPARQL-BGP"
    return "\n".join([f"% {rule.short_key}: {label} ({tag})"] + head_lines)


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
