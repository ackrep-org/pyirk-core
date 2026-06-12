"""
H5 SPARQL Stage 1 — Aequivalenz pro neu delegierter SPARQL-BGP-Praemissen-Regel.

Stage 1 deckt das pure-BGP-Fragment der SPARQL-Praemissen ab (siehe
``experiments/h5_sparql/recon.md``):

  * I798 — kleinstes BGP (4 Tripel, 1 Boolean-Literal-Konstante).

Spaetere Stufen (2/4/5) erweitern das Akzeptanzfragment um BGP+Literal-only
Regeln (I730/I792), den Sonderfall I725, Inequality-Filter (I710/I740/I803)
und stratifizierte Negation (I741). Jede neu delegierte Regel bekommt hier
einen eigenen Test, gleicher Stil wie ``test_h5_extension_literal_premises``:
zweimal apply_semantic_rules — einmal nativ (Flag aus), einmal delegiert
(``PYIRK_NEMO_DELEGATION=1``) — und Multiset-Vergleich der neu erzeugten
Statements (Dup-Multiset-Aequivalenz wie Gate 3 in Phase 2.1).

Fixture-Hinweis I798: Auf der zebra-only-KB allein erzeugt I798 NULL neue
Statements (kein ?p1 R50 ?p2 vorhanden) — ein Vergleich waere trivial. Das
``zebra02``-Puzzle-Modul liefert die benoetigten Personen-Tripel; zwei
Prerequisite-Regeln (I702 reverse-statements und I705 different-from)
populieren die R50-Facts. Beide Regeln laufen *vor* der Messung — in nativem
wie in delegierten Subprozess identisch, sodass der Ausgangszustand gleich
ist. Die Messung gilt dann ausschliesslich I798.

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
    """One test per SPARQL-BGP rule that the Stage-1 H5 SPARQL extension
    moves from ``python_only`` to ``direct``.

    Stage-1 verdict (see ``experiments/h5_sparql/recon.md``):
      * I798 is the smallest pure BGP (4 triples, one Boolean-literal
        constant) and is the only rule covered by this stage.
      * I725/I730/I792 are also pure BGP and are translated by the same code
        path, but their tests come in Stage 2 (with I725 honest-stopped due
        to a native AssertionError on object positions binding to literals).
      * I710/I740/I803 carry ``FILTER(?x != ?y)`` and stay ``python_only``
        until Stage 4 (inequality-constraint translation).
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
        # pass without proving anything. The Stage-1 fixture is sized so
        # that I798 actually fires (~20 new statements on zebra02 after
        # I702/I705 prereqs); if it ever returns empty we fail fast rather
        # than silently green.
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


if __name__ == "__main__":
    unittest.main()
