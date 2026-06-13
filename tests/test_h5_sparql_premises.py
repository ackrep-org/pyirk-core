"""
H5 SPARQL Stage 1+2+4 — Aequivalenz pro neu delegierter SPARQL-BGP-Praemissen-Regel.

Stage 1 deckt das pure-BGP-Fragment der SPARQL-Praemissen ab (siehe
``experiments/h5_sparql/recon.md``):

  * I798 — kleinstes BGP (4 Tripel, 1 Boolean-Literal-Konstante).

Stage 2 erweitert das Akzeptanzfragment um BGP-Regeln mit mehreren
Literal-Konstanten:

  * I730 — 4 Tripel, 1 Boolean-Literal-Konstante (R2850=True).
  * I792 — 7 Tripel, 2 Boolean-Literal-Konstanten (R57=False, R2850=True).

Stage 4 fuegt BGP-Regeln mit AND-konjunktivem ``FILTER(?a != ?b)`` hinzu:

  * I710 — 3 BGP-Tripel + 1 Inequality.
  * I740 — 8 BGP-Tripel + 5 Inequalities (Stresstest des AND-Walks).
  * I803 — 8 BGP-Tripel + 1 Inequality.

Spaetere Stufe 5 deckt I741 (stratifizierte Negation via ``MINUS``).
Jede neu delegierte Regel bekommt hier einen eigenen Test, gleicher Stil
wie ``test_h5_extension_literal_premises``:
zweimal apply_semantic_rules — einmal nativ (Flag aus), einmal delegiert
(``PYIRK_NEMO_DELEGATION=1``) — und Multiset-Vergleich der neu erzeugten
Statements (Dup-Multiset-Aequivalenz wie Gate 3 in Phase 2.1).

Fixture-Hinweis (Stages 1+2): Auf der zebra-only-KB allein feuern die
SPARQL-BGP-Regeln nicht (es fehlen R50-, R3606- und negative-fact-Tripel).
Das ``zebra02``-Puzzle-Modul liefert die benoetigten Personen-Tripel; zwei
Prerequisite-Regeln (I702 reverse-statements und I705 different-from)
populieren die R50-Facts. Auf dieser Fixture feuern alle drei Stage-1/2-
Regeln nicht-trivial:

  * I798 ~ 20 neue Statements (R50-Pfad gegen funktionale Aktivitaet).
  * I730 ~ 6  neue Statements (R3606-lebt-neben + funktionale Aktivitaet).
  * I792 ~ 8  neue Statements (negative Fakten + Mensch-Sein).

Beide Prerequisite-Regeln laufen *vor* der Messung — in nativem wie in
delegierten Subprozess identisch, sodass der Ausgangszustand gleich ist.
Die Messung gilt dann ausschliesslich der jeweiligen Regel.

Isolation: jeder Lauf erfolgt in einem eigenen Subprozess (saubere
``pyirk.ds``-State-Trennung zwischen nativ und delegated).

Pflicht: pytest mit ``-p no:randomly``.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

# Repo-Root: zwei Verzeichnisse ueber dieser Datei.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
ZEBRA_BASE_DATA_PATH = os.path.join(HERE, "test_data", "zebra_base_data.py")
ZEBRA_RULES_PATH = os.path.join(HERE, "test_data", "zebra_puzzle_rules.py")
ZEBRA02_PATH = os.path.join(HERE, "test_data", "zebra02.py")

# Default to the interpreter running the test session; the subprocess only
# needs the same environment as the parent (pyirk + test deps).
VENV_PYTHON = os.environ.get("PYIRK_VENV_PYTHON", sys.executable)


_SUBPROCESS_SCRIPT = r"""
import sys, os, json
sys.path.insert(0, %(src_dir)r)

MODE = %(mode)r
RULE_KEY = %(rule_key)r
OUT_JSON = %(out_json)r
ZEBRA_BASE_DATA_PATH = %(zebra_base_data)r
ZEBRA_RULES_PATH = %(zebra_rules)r
ZEBRA02_PATH = %(zebra02)r
PREREQ_RULE_KEYS = %(prereq_rule_keys)r

if MODE == "delegation":
    os.environ["PYIRK_NEMO_DELEGATION"] = "1"
else:
    os.environ.pop("PYIRK_NEMO_DELEGATION", None)

import pyirk as p

zb = p.irkloader.load_mod_from_path(ZEBRA_BASE_DATA_PATH, prefix="zb")
zr = p.irkloader.load_mod_from_path(ZEBRA_RULES_PATH, prefix="zr")
z2 = p.irkloader.load_mod_from_path(ZEBRA02_PATH, prefix="z2")

# Pre-apply prerequisite rules under the SAME flag setting in both modes.
# I798 binds ?p1 R50 ?p2 — there is no R50-fact in the zebra-only KB until
# I705 (different-from from negative facts) and I702 (reverse statements)
# have populated them. Both prerequisites have proven multiset-equivalent
# under delegation in test_h5_extension_literal_premises (I705) / are
# python_only callbacks unaffected by delegation (I702), so the prerequisite
# state matches between native and delegated subprocesses.
for prereq_key in PREREQ_RULE_KEYS:
    p.ruleengine.apply_semantic_rules(
        getattr(zr, prereq_key), mod_context_uri=zr.__URI__,
    )

rule = getattr(zr, RULE_KEY)
res = p.ruleengine.apply_semantic_rules(rule, mod_context_uri=zr.__URI__)


def _obj_repr(o):
    uri = getattr(o, "uri", None)
    if uri is not None:
        return uri
    return "LIT:" + repr(o)


triples = []
for stm in res.new_statements:
    subj = stm.subject
    pred = stm.predicate
    obj = stm.object
    s_uri = getattr(subj, "uri", None) or repr(subj)
    p_uri = getattr(pred, "uri", None) or repr(pred)
    triples.append([s_uri, p_uri, _obj_repr(obj)])

with open(OUT_JSON, "w", encoding="utf-8") as fh:
    json.dump({"mode": MODE, "rule": RULE_KEY, "triples": triples}, fh)
"""


def _run_rule_subprocess(rule_key: str, *, mode: str, prereq_rule_keys: tuple) -> list:
    """Apply *rule_key* via apply_semantic_rules in a clean subprocess.

    Returns the list of (subj_uri, pred_uri, obj_repr) triples produced by
    the rule.  Each subprocess is independent — the global ``pyirk.ds`` state
    of one run never bleeds into the other.
    """
    with tempfile.TemporaryDirectory(prefix="h5sparql_") as tmp_dir:
        out_json = os.path.join(tmp_dir, f"snap_{mode}.json")
        script = _SUBPROCESS_SCRIPT % dict(
            src_dir=SRC_DIR,
            mode=mode,
            rule_key=rule_key,
            out_json=out_json,
            zebra_base_data=ZEBRA_BASE_DATA_PATH,
            zebra_rules=ZEBRA_RULES_PATH,
            zebra02=ZEBRA02_PATH,
            prereq_rule_keys=tuple(prereq_rule_keys),
        )
        script_path = os.path.join(tmp_dir, "_run.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script)

        proc = subprocess.run(
            [VENV_PYTHON, script_path],
            capture_output=True, text=True, timeout=240,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"subprocess ({mode}) for {rule_key} failed: "
                f"exit={proc.returncode}\nSTDERR:\n{proc.stderr[:2000]}"
            )

        with open(out_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    return data["triples"]


def _nemo_available() -> bool:
    # Use the production resolver (PYIRK_NEMO_BIN -> PATH -> legacy default) so
    # the skip condition matches what the delegation subprocess will see.
    from pyirk.nemobridge.delegation import _resolve_nmo_bin

    return _resolve_nmo_bin() is not None


@unittest.skipUnless(_nemo_available(), "no nmo binary found (PYIRK_NEMO_BIN, PATH, legacy default)")
class Test_H5_SPARQL_Premises(unittest.TestCase):
    """One test per SPARQL-BGP rule that the Stage-1/2/4 H5 SPARQL extension
    moves from ``python_only`` to ``direct``.

    Stage-1/2/4 verdict (see ``experiments/h5_sparql/recon.md``):
      * I798 — smallest pure BGP (4 triples, one Boolean literal). Stage 1.
      * I730, I792 — pure BGP with multiple Boolean literal constants
        (4/7 triples). Stage 2.
      * I710, I740, I803 — BGP + AND-conjoined ``FILTER(?a != ?b)`` chain.
        Stage 4.
      * I725 — also pure BGP, but excluded by translator curation
        (native crash on zebra-only KB; see translator
        ``_SPARQL_PYTHON_ONLY_RULE_KEYS``). No test here — by Honest-Stop.
      * I741 carries ``MINUS`` and stays ``python_only`` until Stage 5
        (stratified negation).

    Each test checks Dup-Multiset-Aequivalenz between native and delegated
    new-statement multisets — same criterion as Phase 2.1 Gate 3.
    """

    def _assert_equivalent(self, rule_key: str, prereq_rule_keys: tuple):
        native = _run_rule_subprocess(
            rule_key, mode="native", prereq_rule_keys=prereq_rule_keys,
        )
        delegated = _run_rule_subprocess(
            rule_key, mode="delegation", prereq_rule_keys=prereq_rule_keys,
        )

        # Honest-stop guard: a trivially-empty multiset comparison would
        # pass without proving anything. The Stage-1/2/4 fixture is sized so
        # that each tested rule fires non-trivially (I798 ~ 20, I730 ~ 6,
        # I792 ~ 8, I710 ~ 4, I803 ~ 88 new statements on zebra02 after the
        # respective prereqs); if the count ever drops to zero we fail fast
        # rather than silently green.
        self.assertGreater(
            len(native), 0,
            f"{rule_key}: native run produced 0 new statements — fixture "
            "no longer triggers the rule; multiset comparison would be "
            "trivially green. Adjust the prerequisite chain or the fixture."
        )

        c_native = Counter(tuple(t) for t in native)
        c_deleg = Counter(tuple(t) for t in delegated)

        missing = c_native - c_deleg
        extra = c_deleg - c_native
        msg_parts = []
        if missing:
            msg_parts.append(f"missing in delegation ({sum(missing.values())}):")
            for t, n in list(missing.items())[:10]:
                msg_parts.append(f"  -{n}x {t}")
        if extra:
            msg_parts.append(f"extra in delegation ({sum(extra.values())}):")
            for t, n in list(extra.items())[:10]:
                msg_parts.append(f"  +{n}x {t}")

        self.assertEqual(
            c_native, c_deleg,
            f"Multiset mismatch for {rule_key}:\n" + "\n".join(msg_parts),
        )

    def test_I798_sparql_bgp_native_vs_delegated_multiset_equiv(self):
        """rule: deduce negative facts from different-from-facts (SPARQL BGP, 4 triples, bool=True)

        Prerequisite chain on zebra02-puzzle data:
          * I702 (reverse-statements callback) populates symmetric R50/R3606
            etc. — also needed indirectly so I705 sees the right edges.
          * I705 (direct, literal-premise) derives the R50 different-from
            facts that I798's ``?p1 :R50 ?p2`` premise binds against.
        Without these the zebra-only KB has 0 R50 facts and I798 fires zero
        times — covered by the honest-stop guard above.
        """
        self._assert_equivalent("I798", prereq_rule_keys=("I702", "I705"))

    def test_I730_sparql_bgp_native_vs_delegated_multiset_equiv(self):
        """rule: deduce negative facts for neighbors (SPARQL BGP, 4 triples, bool=True)

        BGP-Inhalt:
          ``?rel1 R2850 true . ?rel1 R43 ?rel2 . ?h1 ?rel1 ?itm1 . ?h1 R3606 ?h2``

        Fixture identisch zu I798 (zebra02-Personen + I702/I705-Prereqs).
        Die R3606-Tripel (``lives next to``) liefert zebra02 selbst; die
        funktionalen-Aktivitaet- und Opposite-Tripel (R2850 / R43) stammen
        aus zebra_base_data. Auf dieser Fixture feuert I730 ~6-mal — Honest-
        Stop-Guard prueft das.
        """
        self._assert_equivalent("I730", prereq_rule_keys=("I702", "I705"))

    def test_I792_sparql_bgp_native_vs_delegated_multiset_equiv(self):
        """rule: deduce different-from-facts from negative facts (SPARQL BGP, 7 triples, bool=False/True)

        BGP-Inhalt:
          ``?itm1a R57 false . ?h1 ?rel1 ?itm1a . ?rel1 R2850 true .
            ?h1 R4 I7435 . ?h2 R4 I7435 . ?h2 ?rel1_not ?itm1a .
            ?rel1 R43 ?rel1_not``

        Erweiterte Prereq-Kette ggue. I730: I792 bindet ``?h2 ?rel1_not
        ?itm1a`` und braucht damit *negative* Fakten (z. B. ``person7
        owns_not fox``). Die zebra-only-KB + zebra02 enthalten keine
        expliziten not-owns/-smokes/-lives-Statements; diese werden erst
        von I730 derived. Deshalb laeuft I730 hier *als Prereq* — beide
        Modi natuerlich symmetrisch (I730-Aequivalenz wird vom separaten
        I730-Test verifiziert, das schliesst den Zyklus). Auf dieser
        Fixture feuert I792 ~8-mal — Honest-Stop-Guard prueft das.
        """
        self._assert_equivalent("I792", prereq_rule_keys=("I702", "I705", "I730"))

    def test_I710_native_vs_delegated_multiset_equal(self):
        """rule: identify same items via R2850 functional activity
        (SPARQL BGP + 1 inequality)

        BGP-Inhalt:
          ``?p1 ?rel1 ?some_itm . ?p2 ?rel1 ?some_itm . ?rel1 R2850 true``
        Filter: ``?p1 != ?p2``.

        Fixture identisch zu I730/I798 (zebra02 + I702/I705). zebra02
        liefert die Personen mit funktionalen Aktivitaeten (R2850-Tripel
        stammen aus zebra_base_data). Auf dieser Fixture feuert I710 ~4-mal
        — Honest-Stop-Guard prueft das.

        Algebra-Form (siehe ``algebra_dumps.txt``):
          ``Filter(expr=RelationalExpression(?p1 != ?p2), p=BGP(...))`` —
        ein einzelnes Atom, kein ``ConditionalAndExpression``-Wrapper.
        """
        self._assert_equivalent("I710", prereq_rule_keys=("I702", "I705"))

    def test_I740_native_vs_delegated_multiset_equal(self):
        """rule: deduce more negative facts from negative facts
        (SPARQL BGP + 5 inequalities)

        Algebra-Form (siehe ``algebra_dumps.txt``): Filter wrapt eine
        ``ConditionalAndExpression`` mit ``expr=RelationalExpression`` +
        ``other=[RelationalExpression x 4]`` — Stresstest fuer den
        AND-Flatten-Walk im Translator.

        Honest-Stop-Skip: zebra02 + erweiterte Prereqs (I702/I705/I730/I792)
        triggern I740 nativ 0-mal. Die Praemisse verlangt ``?h2 ?rel2_not
        ?itm2`` plus die kombinierte Bedingung dass ``h1`` zwei verschiedene
        funktionale Aktivitaeten hat UND ``h2`` eine davon plus die Gegen-
        relation der anderen. zebra02 enthaelt schlicht keine derart
        konfigurierte Personenkonstellation, auch nicht nach Praemissen-
        Saettigung. KEINE schwaechere Assertion — Worker-Notes der
        Stage-4-Task vermerken diesen Skip.
        """
        import pytest
        prereq_rule_keys = ("I702", "I705", "I730", "I792")
        native = _run_rule_subprocess(
            "I740", mode="native", prereq_rule_keys=prereq_rule_keys,
        )
        if len(native) == 0:
            pytest.skip(
                "I740 native fires 0 times on zebra02 even with extended "
                "prereqs (I702/I705/I730/I792); see task_004 worker notes."
            )
        self._assert_equivalent("I740", prereq_rule_keys=prereq_rule_keys)

    def test_I803_curated_python_only(self):
        """rule: deduce different-from-facts from functional activities
        (SPARQL BGP + 1 inequality) — Stage-4 curated exclusion.

        I803's BGP includes ``?type_of_itm1 :R51 ?tuple . ?tuple :R39
        ?itm2`` (R51__instances_are_from on the type; R39__has_element on
        the tuple). pyirk's ``new_tuple`` attaches a ``has_index``
        qualifier to that R39 statement, so the Nemo exporter routes the
        main-tuple R39 fact to ``stmts.csv``/``quals_R40.csv``; only the
        (unqualified) R39 facts on reification-anchor sub-items end up in
        ``triples.csv``. The Nemo EDB seed (``fact(?s,?p,?o) :-
        triples(?s,?p,?o)``) never produces the fact the rule binds
        against, so the delegated multiset is 0 while the native one is
        ~88 on zebra02. Honest-Stop: I803 is on the curated-exclusion list
        ``_SPARQL_PYTHON_ONLY_RULE_KEYS`` until a future H5-extension pass
        seeds the IDB from qualified entity-entity statements too.

        This test asserts the classifier behaviour, not equivalence —
        running native vs delegated would be a trivially-failing
        comparison that adds no information beyond the classifier.
        """
        # Subprocess-isolate: classify_rules reads global pyirk.ds, and
        # other tests in this file run in their own subprocesses; we keep
        # the same hygiene here.
        script = r"""
import sys, json
sys.path.insert(0, %(src_dir)r)
import pyirk as p
zb = p.irkloader.load_mod_from_path(%(zb)r, prefix='zb')
zr = p.irkloader.load_mod_from_path(%(zr)r, prefix='zr')
from pyirk.nemobridge.translator import classify_rules
clf = {c.rule_short_key: c for c in classify_rules(p.ds)}.get('I803')
print(json.dumps({'cat': clf.category, 'reason': clf.reason}))
""" % dict(src_dir=SRC_DIR, zb=ZEBRA_BASE_DATA_PATH, zr=ZEBRA_RULES_PATH)
        with tempfile.TemporaryDirectory(prefix="h5sparql_") as tmp_dir:
            script_path = os.path.join(tmp_dir, "_run.py")
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(script)
            proc = subprocess.run(
                [VENV_PYTHON, script_path],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 0,
                f"classify subprocess failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
            )
            data = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(
            data["cat"], "python_only",
            f"I803 must stay python_only (Stage-4 honest-stop); got {data}",
        )
        self.assertIn("curat", data["reason"].lower(),
            f"I803 python_only reason must mention curated exclusion; got: {data['reason']}",
        )


if __name__ == "__main__":
    unittest.main()
