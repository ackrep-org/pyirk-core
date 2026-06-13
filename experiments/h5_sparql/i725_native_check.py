#!/usr/bin/env python3
"""i725_native_check.py — reproduce the native crash of I725 on the zebra-only KB.

Loads `zebra_base_data` (prefix ``zb``) and `zebra_puzzle_rules`
(prefix ``zr``) via ``pyirk.irkloader``, then applies the I725 rule alone via
``apply_semantic_rules(I725, mod_context_uri=zr.__URI__)``.

Per `docs/design/h5_extension_report.md` §5.2 / Extension task_004 this is
expected to crash with an ``AssertionError`` somewhere in
``ruleengine.py`` (around line 768, inside the
``isinstance(new_subj, core.Entity)`` assertion) because I725's SPARQL premise
binds object positions that can resolve to RDF literals — which the native
rule engine cannot represent as ``core.Entity`` instances.

Output: full traceback to stdout AND structured one-line summary at the end
so the orchestrator can pull the exception type without parsing the full
trace.  Redirected by callers into ``i725_native_check.log``.
"""

from __future__ import annotations

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
ZEBRA_BASE_DATA_PATH = os.path.join(REPO_ROOT, "tests", "test_data", "zebra_base_data.py")
ZEBRA_RULES_PATH = os.path.join(REPO_ROOT, "tests", "test_data", "zebra_puzzle_rules.py")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Make sure delegation flag is OFF — we are probing native behavior only.
os.environ.pop("PYIRK_NEMO_DELEGATION", None)


def main() -> int:
    import pyirk as p

    zb = p.irkloader.load_mod_from_path(ZEBRA_BASE_DATA_PATH, prefix="zb")  # noqa: F841
    zr = p.irkloader.load_mod_from_path(ZEBRA_RULES_PATH, prefix="zr", reuse_loaded=True)

    rule = zr.I725
    print(f"loaded rule {rule.short_key}: {rule.R1__has_label}")
    print(f"premise SPARQL source:")
    src = rule.scp__premise.get_relations("R63__has_SPARQL_source", return_obj=True)
    print(src[0] if src else "(no SPARQL source!)")
    print("=" * 70)

    try:
        result = p.ruleengine.apply_semantic_rules(rule, mod_context_uri=zr.__URI__)
        n = len(getattr(result, "new_statements", []) or [])
        print(f"NO CRASH — apply_semantic_rules returned {n} new statements.")
        print(f"SUMMARY: outcome=ok new_statements={n}")
        return 0
    except Exception:  # noqa: BLE001
        print("CRASHED:")
        traceback.print_exc()
        tb = sys.exc_info()[2]
        # walk to the last frame
        last = tb
        while last.tb_next is not None:
            last = last.tb_next
        frame = last.tb_frame
        exc_type = sys.exc_info()[0].__name__
        print()
        print(
            f"SUMMARY: outcome=crash exc={exc_type} "
            f"file={os.path.basename(frame.f_code.co_filename)} "
            f"line={last.tb_lineno} func={frame.f_code.co_name}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
