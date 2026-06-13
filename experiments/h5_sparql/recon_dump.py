#!/usr/bin/env python3
"""recon_dump.py — SPARQL-Algebra-Recon der 8 Zebra-Regeln mit R63-Praemisse.

Laedt die Zebra-Module (zebra_base_data, zebra_puzzle_rules), liest pro Regel
die SPARQL-Quelle aus ``R63__has_SPARQL_source``, parsed sie mit
``rdflib.plugins.sparql.parser.parseQuery`` plus
``rdflib.plugins.sparql.algebra.translateQuery`` und klassifiziert die
Algebra in eine der vier Klassen:

  - ``bgp_pure``        — Algebra besteht ausschliesslich aus einem Bgp-Knoten
                          (ggf. eingehuellt in Project/SelectQuery).
  - ``bgp_inequality``  — Bgp + Filter, dessen Filter-Expression eine reine
                          Konjunktion (oder Einzelausdruck) aus ``?x != ?y``
                          zwischen Variablen ist.
  - ``bgp_negation``    — Bgp + Minus, oder Bgp + Filter mit NotExists-Ausdruck.
  - ``unsupported``     — alles andere (Optional, Union, Property-Paths,
                          Aggregation, weitere Filtertypen).

Die Klassifikation arbeitet ausschliesslich auf der rdflib-Algebra, nicht auf
dem Quelltext. Ausgabe:

  - ``algebra_dumps.txt``  — pprintAlgebra je Regel (komplett).
  - ``recon.md``           — deutsche Recon-Zusammenfassung mit Uebersicht.

Aufruf:
    /home/user/venvs/pyirk-core-venv/bin/python experiments/h5_sparql/recon_dump.py

(Override des Interpreters via PYIRK_VENV_PYTHON moeglich.)
"""

from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
ZEBRA_BASE_DATA_PATH = os.path.join(REPO_ROOT, "tests", "test_data", "zebra_base_data.py")
ZEBRA_RULES_PATH = os.path.join(REPO_ROOT, "tests", "test_data", "zebra_puzzle_rules.py")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pyirk as p  # noqa: E402
from rdflib.plugins.sparql.parser import parseQuery  # noqa: E402
from rdflib.plugins.sparql.algebra import translateQuery, pprintAlgebra  # noqa: E402
from rdflib.term import Variable, URIRef, Literal  # noqa: E402


RULE_KEYS = ("I710", "I725", "I730", "I740", "I741", "I792", "I798", "I803")


def _build_prefix_block() -> str:
    """Build the same prefix block the engine prepends before SPARQL queries."""
    prefixes = []
    for mod_uri, prefix in p.ds.uri_prefix_mapping.a.items():
        if mod_uri == p.settings.BUILTINS_URI:
            prefix = ""
        prefixes.append(f"PREFIX {prefix}: <{mod_uri}#>")
    return "\n".join(prefixes)


def _build_query_text(rule, prefix_block: str) -> tuple[str, list[str]]:
    """Reproduce the engine's wrapped query string (PREFIX + SELECT + WHERE)."""
    import textwrap

    sparql_src = rule.scp__premise.get_relations("R63__has_SPARQL_source", return_obj=True)
    assert sparql_src, f"rule {rule.short_key} has no SPARQL premise"
    where_clause = textwrap.dedent(sparql_src[0])

    # the engine uses ra_workers[0].local_node_names; we approximate it via
    # variables created in the setting scope (the engine does likewise).
    var_names = _collect_select_vars(rule)
    select_clause = "SELECT " + " ".join("?" + v for v in var_names)
    return f"{prefix_block}\n{select_clause}\n{where_clause}", var_names


def _collect_select_vars(rule) -> list[str]:
    """Pull variable names from the setting scope (R23-defined entities + rel-vars).

    We don't need to reproduce the engine's variable order exactly — translateQuery
    classifies the algebra regardless of which projection vars we pick, as long as
    they appear in the WHERE clause.  Picking *all* variables present in the
    setting scope is the safe choice.
    """
    setting = rule.scp__setting
    items = setting.get_inv_relations("R20__has_defining_scope", return_subj=True)
    names = []
    for it in items:
        lbl = getattr(it, "R23__has_name_in_scope", None) or it.R1__has_label
        # the engine uses R23__has_name_in_scope for SPARQL variables; fall back
        # to the short label otherwise.
        if isinstance(lbl, str) and lbl.startswith("?"):
            lbl = lbl[1:]
        if isinstance(lbl, str) and " " not in lbl:
            names.append(lbl)
    # dedup, keep order
    seen = set()
    ordered = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        ordered.append(n)
    return ordered


# ─────────────────────────────────────────────────────────────────────────────
# Algebra classification
# ─────────────────────────────────────────────────────────────────────────────

class AlgebraStats:
    def __init__(self):
        self.bgp_triples = []         # list of (s, p, o) tuples (raw rdflib terms)
        self.filters = []             # list of filter expressions (raw)
        self.has_optional = False
        self.has_union = False
        self.has_minus = False
        self.has_extend = False
        self.has_group = False
        self.has_property_path = False
        self.other_constructs = []    # named string of other unknown constructs


def _walk_algebra(node, stats: AlgebraStats):
    """Recursively walk the algebra tree and capture structural facts."""
    from rdflib.plugins.sparql.algebra import CompValue

    if not isinstance(node, CompValue):
        return

    name = node.name
    if name in ("BGP", "Bgp"):
        for triple in node.triples:
            stats.bgp_triples.append(triple)
    elif name == "Filter":
        stats.filters.append(node.expr)
        _walk_algebra(node.p, stats)
    elif name == "Project":
        _walk_algebra(node.p, stats)
    elif name == "SelectQuery":
        _walk_algebra(node.p, stats)
    elif name == "Slice":
        _walk_algebra(node.p, stats)
    elif name == "Distinct":
        _walk_algebra(node.p, stats)
    elif name == "Reduced":
        _walk_algebra(node.p, stats)
    elif name == "OrderBy":
        _walk_algebra(node.p, stats)
    elif name == "ToList":
        _walk_algebra(node.p, stats)
    elif name == "LeftJoin":
        stats.has_optional = True
        _walk_algebra(node.p1, stats)
        _walk_algebra(node.p2, stats)
    elif name == "Union":
        stats.has_union = True
        _walk_algebra(node.p1, stats)
        _walk_algebra(node.p2, stats)
    elif name == "Minus":
        stats.has_minus = True
        _walk_algebra(node.p1, stats)
        # the negated pattern itself is also walked so triples in it are
        # exposed for inspection, but the *containing* construct stays Minus.
        _walk_algebra(node.p2, stats)
    elif name == "Join":
        _walk_algebra(node.p1, stats)
        _walk_algebra(node.p2, stats)
    elif name == "Extend":
        stats.has_extend = True
        _walk_algebra(node.p, stats)
    elif name in ("Group", "AggregateJoin"):
        stats.has_group = True
        _walk_algebra(getattr(node, "p", None), stats)
    else:
        stats.other_constructs.append(name)
        for sub in ("p", "p1", "p2"):
            child = getattr(node, sub, None)
            if child is not None:
                _walk_algebra(child, stats)


def _is_var_neq_var(expr) -> bool:
    """True iff expr is of the form ?x != ?y between two Variables."""
    from rdflib.plugins.sparql.parserutils import CompValue

    if not isinstance(expr, CompValue):
        return False
    if expr.name != "RelationalExpression":
        return False
    if str(expr.op) != "!=":
        return False
    return isinstance(expr.expr, Variable) and isinstance(expr.other, Variable)


def _flatten_and(expr):
    """Yield conjuncts of `expr` (treating ConditionalAndExpression as &&)."""
    from rdflib.plugins.sparql.parserutils import CompValue

    if isinstance(expr, CompValue) and expr.name == "ConditionalAndExpression":
        yield from _flatten_and(expr.expr)
        for other in expr.other or []:
            yield from _flatten_and(other)
    else:
        yield expr


def _filter_is_pure_inequality(filters) -> bool:
    """True iff every filter is a conjunction of `?x != ?y` between variables."""
    if not filters:
        return False
    for f in filters:
        for conj in _flatten_and(f):
            if not _is_var_neq_var(conj):
                return False
    return True


def _filter_has_notexists(filters) -> bool:
    from rdflib.plugins.sparql.parserutils import CompValue

    def _walk(e):
        if isinstance(e, CompValue):
            if e.name == "Builtin_NOTEXISTS":
                return True
            for v in e.values() if hasattr(e, "values") else []:
                pass
            for k in list(e.keys()):
                if _walk(e[k]):
                    return True
        if isinstance(e, list):
            return any(_walk(x) for x in e)
        return False

    return any(_walk(f) for f in filters)


def _has_property_path(triples) -> bool:
    """A property-path predicate is wrapped in a `Path` CompValue (or similar)."""
    from rdflib.plugins.sparql.parserutils import CompValue
    from rdflib.paths import Path

    for s, pp, o in triples:
        if isinstance(pp, Path):
            return True
        if isinstance(pp, CompValue):
            return True
    return False


def classify(stats: AlgebraStats) -> tuple[str, list[str]]:
    """Map structural facts to one of the four classes plus a reason list."""
    reasons = []
    if stats.has_optional:
        reasons.append("LeftJoin/OPTIONAL")
    if stats.has_union:
        reasons.append("Union")
    if stats.has_extend:
        reasons.append("Extend/BIND")
    if stats.has_group:
        reasons.append("Group/Aggregation")
    if stats.other_constructs:
        reasons.append("other: " + ", ".join(sorted(set(stats.other_constructs))))
    if _has_property_path(stats.bgp_triples):
        reasons.append("Property-Path im Praedikat")

    if reasons:
        return "unsupported", reasons

    if stats.has_minus:
        return "bgp_negation", ["Minus-Subpattern vorhanden"]
    if _filter_has_notexists(stats.filters):
        return "bgp_negation", ["Filter mit NotExists"]
    if stats.filters:
        if _filter_is_pure_inequality(stats.filters):
            return "bgp_inequality", [f"{len(stats.filters)} reine != Filter"]
        else:
            return "unsupported", ["Filter ist kein reines !=/NotExists"]
    return "bgp_pure", ["nur BGP"]


# ─────────────────────────────────────────────────────────────────────────────
# Triple / Literal extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_literals(triples) -> list[tuple[str, str]]:
    """Return (python-type, repr) for every Literal occurring as s/p/o."""
    out = []
    for s, pp, o in triples:
        for term in (s, pp, o):
            if isinstance(term, Literal):
                py = term.toPython()
                out.append((type(py).__name__, repr(py)))
    return out


def triple_summary(triples) -> list[str]:
    """Render each triple in (s p o) shorthand for the recon document."""
    def short(t):
        if isinstance(t, Variable):
            return "?" + str(t)
        if isinstance(t, URIRef):
            s = str(t)
            # truncate long URIs for legibility
            if "#" in s:
                return s.rsplit("#", 1)[-1]
            return s.rsplit("/", 1)[-1]
        if isinstance(t, Literal):
            return f"{t.toPython()!r}^^{type(t.toPython()).__name__}"
        return repr(t)

    return [f"{short(s)}  {short(pp)}  {short(o)}" for s, pp, o in triples]


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # Load the zebra modules in the same way the existing extension test does.
    zb = p.irkloader.load_mod_from_path(ZEBRA_BASE_DATA_PATH, prefix="zb")
    zr = p.irkloader.load_mod_from_path(ZEBRA_RULES_PATH, prefix="zr", reuse_loaded=True)

    prefix_block = _build_prefix_block()

    out_dumps = os.path.join(HERE, "algebra_dumps.txt")
    out_md = os.path.join(HERE, "recon.md")

    per_rule_data = []

    with open(out_dumps, "w", encoding="utf-8") as fh_dumps:
        for key in RULE_KEYS:
            rule = getattr(zr, key)
            qtext, sel_vars = _build_query_text(rule, prefix_block)

            fh_dumps.write("=" * 78 + "\n")
            fh_dumps.write(f"Rule {key} — projected vars: {sel_vars}\n")
            fh_dumps.write("-" * 78 + "\n")
            fh_dumps.write(qtext + "\n")
            fh_dumps.write("-" * 78 + "\n")

            try:
                parsed = parseQuery(qtext)
                algebra = translateQuery(parsed)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    pprintAlgebra(algebra)
                pp_text = buf.getvalue()
                fh_dumps.write(pp_text + "\n")
            except Exception as exc:
                fh_dumps.write(f"!! parse/translate failed: {exc!r}\n")
                per_rule_data.append({
                    "key": key,
                    "classification": "unsupported",
                    "reasons": [f"parse error: {exc!r}"],
                    "triples": [],
                    "filters": [],
                    "literals": [],
                    "sparql_src": rule.scp__premise.get_relations(
                        "R63__has_SPARQL_source", return_obj=True)[0],
                })
                continue

            stats = AlgebraStats()
            _walk_algebra(algebra.algebra, stats)
            cls, reasons = classify(stats)

            per_rule_data.append({
                "key": key,
                "classification": cls,
                "reasons": reasons,
                "triples": triple_summary(stats.bgp_triples),
                "filter_count": len(stats.filters),
                "has_minus": stats.has_minus,
                "has_notexists": _filter_has_notexists(stats.filters),
                "literals": extract_literals(stats.bgp_triples),
                "sparql_src": rule.scp__premise.get_relations(
                    "R63__has_SPARQL_source", return_obj=True)[0],
            })

    # ─── write recon.md ────────────────────────────────────────────────────
    lines = []
    lines.append("# H5 SPARQL Recon (Stufe 0)\n")
    lines.append(
        "Klassifikation der 8 Zebra-Regeln mit `R63__has_SPARQL_source` auf Basis\n"
        "der **rdflib-Algebra** (keine Regex auf Quelltext). Erzeugt durch\n"
        "`experiments/h5_sparql/recon_dump.py`. Volle pprintAlgebra-Dumps in\n"
        "`algebra_dumps.txt`.\n"
    )

    lines.append("## Uebersicht\n")
    lines.append("| Regel | Klasse | #Tripel | #Filter | Minus | NotExists | Literale |")
    lines.append("|-------|--------|---------|---------|-------|-----------|----------|")
    for d in per_rule_data:
        ltxt = "; ".join(f"{t}={v}" for t, v in d.get("literals", [])) or "—"
        lines.append(
            f"| {d['key']} | `{d['classification']}` | {len(d.get('triples', []))} "
            f"| {d.get('filter_count', 0)} | {'ja' if d.get('has_minus') else 'nein'} "
            f"| {'ja' if d.get('has_notexists') else 'nein'} | {ltxt} |"
        )
    lines.append("")

    for d in per_rule_data:
        lines.append(f"## {d['key']} — `{d['classification']}`\n")
        lines.append("**Klassifikations-Begruendung (aus Algebra):**")
        for r in d["reasons"]:
            lines.append(f"- {r}")
        lines.append("")
        lines.append(f"- Tripel-Anzahl im BGP: **{len(d.get('triples', []))}**")
        lines.append(f"- Filter (Top-Level): **{d.get('filter_count', 0)}**")
        lines.append(f"- Minus-Subpattern: **{'ja' if d.get('has_minus') else 'nein'}**")
        lines.append(f"- NotExists-Filter: **{'ja' if d.get('has_notexists') else 'nein'}**")
        if d.get("literals"):
            lines.append("- Literal-Konstanten:")
            for t, v in d["literals"]:
                lines.append(f"  - `{v}` ({t})")
        else:
            lines.append("- Literal-Konstanten: keine")
        lines.append("")
        if d.get("triples"):
            lines.append("### BGP-Tripel\n```")
            for t in d["triples"]:
                lines.append(t)
            lines.append("```\n")
        lines.append("### SPARQL-Quelltext\n```sparql")
        lines.append(d["sparql_src"].strip())
        lines.append("```\n")

    # ─── sanity-check section ────────────────────────────────────────────
    lines.append("## Sanity der rdflib-Klassifikation\n")
    lines.append(
        "Erwartungen aus `docs/design/h5_extension_report.md` §5.1 (I798 = 4 Tripel "
        "BGP + Literal-Konstante) und der Aufgabenstellung selbst.\n"
    )
    by_key = {d["key"]: d for d in per_rule_data}
    sanity_expectations = [
        ("I798", "bgp_pure"),
        ("I710", "bgp_inequality"),
        ("I741", "bgp_negation"),
    ]
    lines.append("| Regel | erwartet | erkannt | Match |")
    lines.append("|-------|----------|---------|-------|")
    for key, expected in sanity_expectations:
        got = by_key[key]["classification"]
        ok = "ja" if got == expected else "NEIN"
        lines.append(f"| {key} | `{expected}` | `{got}` | {ok} |")
    lines.append("")

    # ─── I725 native crash section (filled in from i725_native_check.log) ─
    log_path = os.path.join(HERE, "i725_native_check.log")
    lines.append("## I725 — Native-Verhalten auf zebra-only-KB\n")
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as fh:
            log_txt = fh.read()
        summary_lines = [l for l in log_txt.splitlines() if l.startswith("SUMMARY:")]
        if summary_lines:
            lines.append(f"`{summary_lines[-1]}`\n")
        # Pull the last AssertionError frame from the traceback for the report.
        # Strip the absolute repo prefix so the curated report stays
        # host-agnostic (raw log keeps the full paths).
        tb_lines = log_txt.splitlines()
        for i, l in enumerate(tb_lines):
            if "AssertionError" in l and "assert isinstance(new_subj" in "".join(tb_lines[max(0, i - 2):i + 1]):
                ctx = [
                    l.replace(REPO_ROOT + "/", "")
                    for l in tb_lines[max(0, i - 4): i + 1]
                ]
                lines.append("Letzter Traceback-Frame:\n```\n" + "\n".join(ctx) + "\n```\n")
                break
        lines.append(
            "**Fazit:** Wie in `docs/design/h5_extension_report.md` §5.2 dokumentiert "
            "scheitert I725 nativ mit `AssertionError` (`isinstance(new_subj, core.Entity)` "
            "in `ruleengine.py:_process_result_map`). I725's SPARQL-Praemisse bindet "
            "Objektpositionen, die nativ zu Literalen aufloesen koennen. Da die native "
            "Engine das Referenz-Orakel ist und auf dieser KB kein wohldefiniertes "
            "Aequivalenzziel existiert, bleibt I725 aus dem Gate-Regelsatz (Stufe 1).\n"
        )
    else:
        lines.append("(`i725_native_check.log` nicht gefunden — bitte erst Skript ausfuehren.)\n")

    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"wrote {out_dumps}")
    print(f"wrote {out_md}")
    print()
    print("Classification summary:")
    for d in per_rule_data:
        print(f"  {d['key']}: {d['classification']:<15s}  reasons={d['reasons']}")


if __name__ == "__main__":
    main()
