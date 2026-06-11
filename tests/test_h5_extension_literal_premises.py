"""
H5 Extension Phase 1 — Aequivalenz pro neu delegierter Literal-Praemissen-Regel.

Fuer jede Regel, die durch die Phase-1-Erweiterung des nemobridge-Translators
neu in den `direct`-Bucket wandert, fuehren wir die Regel einmal nativ und
einmal mit ``PYIRK_NEMO_DELEGATION=1`` aus und vergleichen die Multimenge der
neuen Statements (Dup-Multiset-Aequivalenz wie Gate 3 in Phase 2.1).

Isolation: jeder Lauf erfolgt in einem eigenen Subprozess, sodass der globale
``pyirk.ds``-State zwischen nativ und delegated nicht verschmutzt.

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

# Same path-overlay the equivalence_gate uses to pick up sympy for OCSE; harmless
# for zebra (zebra does not need sympy, but pyirk imports may pull it).
SYMPY_EXTRA = "/home/user/venvs/neo-rag-venv/lib/python3.13/site-packages"

VENV_PYTHON = os.environ.get(
    "PYIRK_VENV_PYTHON", "/home/user/venvs/pyirk-core-venv/bin/python",
)
NEMO_BIN = os.environ.get("PYIRK_NEMO_BIN", "/home/user/bin/nmo")


_SUBPROCESS_SCRIPT = r"""
import sys, os, json
sys.path.insert(0, %(sympy_extra)r)
sys.path.insert(0, %(src_dir)r)

MODE = %(mode)r
RULE_KEY = %(rule_key)r
OUT_JSON = %(out_json)r
ZEBRA_BASE_DATA_PATH = %(zebra_base_data)r
ZEBRA_RULES_PATH = %(zebra_rules)r

if MODE == "delegation":
    os.environ["PYIRK_NEMO_DELEGATION"] = "1"
else:
    os.environ.pop("PYIRK_NEMO_DELEGATION", None)

import pyirk as p

zb = p.irkloader.load_mod_from_path(ZEBRA_BASE_DATA_PATH, prefix="zb")
zr = p.irkloader.load_mod_from_path(ZEBRA_RULES_PATH, prefix="zr")

rule = getattr(zr, RULE_KEY)

# apply_semantic_rules (plural) takes the delegation branch when the flag is on.
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


def _run_rule_subprocess(rule_key: str, *, mode: str) -> list:
    """Apply *rule_key* via apply_semantic_rules in a clean subprocess.

    Returns the list of (subj_uri, pred_uri, obj_repr) triples produced by
    the rule.  Each subprocess is independent — the global ``pyirk.ds`` state
    of one run never bleeds into the other.
    """
    with tempfile.TemporaryDirectory(prefix="h5ext_lit_") as tmp_dir:
        out_json = os.path.join(tmp_dir, f"snap_{mode}.json")
        script = _SUBPROCESS_SCRIPT % dict(
            sympy_extra=SYMPY_EXTRA,
            src_dir=SRC_DIR,
            mode=mode,
            rule_key=rule_key,
            out_json=out_json,
            zebra_base_data=ZEBRA_BASE_DATA_PATH,
            zebra_rules=ZEBRA_RULES_PATH,
        )
        script_path = os.path.join(tmp_dir, "_run.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script)

        proc = subprocess.run(
            [VENV_PYTHON, script_path],
            capture_output=True, text=True, timeout=180,
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
    return os.path.isfile(NEMO_BIN)


@unittest.skipUnless(_nemo_available(), f"Nemo binary missing at {NEMO_BIN}")
class Test_H5_Extension_LiteralPremises(unittest.TestCase):
    """One test per literal-premise rule that the Phase-1 H5 Extension moves
    from ``python_only`` to ``direct``.

    The honest-stop verdict from task_002 is:
      * I702 stays ``python_only`` (assertion = ``reverse_statements`` callback).
      * I705 / I790 / I800 / I820 become ``direct``.

    Each test checks Dup-Multiset-Aequivalenz between the native and delegated
    new-statement multisets — same criterion as Phase 2.1 Gate 3.
    """

    def _assert_equivalent(self, rule_key: str):
        native = _run_rule_subprocess(rule_key, mode="native")
        delegated = _run_rule_subprocess(rule_key, mode="delegation")

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

    def test_I705(self):
        """rule: deduce trivial different-from-facts (literal R57=False premise)"""
        self._assert_equivalent("I705")

    def test_I790(self):
        """rule: infer from 'is one of' -> 'is same as' (literal R38=1 premise)"""
        self._assert_equivalent("I790")

    def test_I800(self):
        """rule: mark relations which are opposite of functional activities
        (literal R2850=True premise, literal True in conclusion)"""
        self._assert_equivalent("I800")

    def test_I820(self):
        """rule: deduce personhood by exclusion (literal R57=True/False ×6 premise)"""
        self._assert_equivalent("I820")


if __name__ == "__main__":
    unittest.main()
