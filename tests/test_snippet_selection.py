"""Tests for ``experiments.fnl_vs_direct.snippet_selection``."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.fnl_vs_direct.snippet_selection import (
    CORPUS_FILES,
    CORPUS_ROOT,
    build_selection,
    tag_snippet,
)


def test_tag_snippet_simple_cases():
    assert tag_snippet("17i", "anything at all") == "ignored"
    assert tag_snippet("3", "There is a class: 'real number'.") == "declaration"
    assert (
        tag_snippet(
            "7",
            "'empty set' is an instance of 'set'.\n"
            "'empty set' has the associated LaTeX notation `$\\varnothing$`.",
        )
        == "instance"
    )
    assert (
        tag_snippet("18", "'partition' is a subclass of 'set'.") == "subclass"
    )
    assert (
        tag_snippet(
            "6",
            "'is element of' has the associated LaTeX notation `$arg1 \\in arg2$`.",
        )
        == "notation"
    )
    assert (
        tag_snippet(
            "12",
            "There is an equivalence-statement:\n"
            "- full source code: ...",
        )
        == "equivalence"
    )
    assert (
        tag_snippet(
            "13",
            "'U' is an instance of 'vector space' qqq univ_quant True",
        )
        == "qualified"
    )
    assert (
        tag_snippet(
            "15",
            "    - AND:\n"
            "        - SX 'is subset of' SY\n"
            "        - SY 'is subset of' SX",
        )
        == "definition_and"
    )
    assert (
        tag_snippet(
            "5",
            "'countable' has the definition:\n"
            "    - OR\n"
            "        - arg1 has the property 'finite'\n"
            "        - arg1 has the property 'countably infinite'",
        )
        == "definition_or"
    )


def _mock_pool() -> dict:
    """A 60-item mock gold pool with a useful type mix and a few ignored."""
    pool = {}
    # 20 light (declarations)
    for i in range(1, 21):
        pool[str(i)] = f"There is a class: 'cls{i}'."
    # 5 ignored
    for i in (21, 22, 23, 24, 25):
        pool[f"{i}i"] = "// ignored content"
    # 10 subclass
    for i in range(26, 36):
        pool[str(i)] = f"'cls{i}' is a subclass of 'set'."
    # 10 notation
    for i in range(36, 46):
        pool[str(i)] = f"'cls{i}' has the associated LaTeX notation $X{i}$."
    # 8 qualified (medium)
    for i in range(46, 54):
        pool[str(i)] = f"'cls{i}' is an instance of 'set' qqq univ_quant True"
    # 4 equivalence (medium)
    for i in range(54, 58):
        pool[str(i)] = "There is an equivalence-statement:\n - full source code: ..."
    # 4 heavy (2 AND, 2 OR)
    pool["58"] = "    - AND:\n        - a\n        - b"
    pool["59"] = "    - AND\n        - a\n        - b"
    pool["60"] = "    - OR\n        - a\n        - b"
    pool["61"] = "    - OR\n        - a\n        - b"
    return pool


def test_build_selection_is_deterministic():
    gold = _mock_pool()
    a = build_selection("nichtlinear", gold=gold, seed=0)
    b = build_selection("nichtlinear", gold=gold, seed=0)
    assert a == b


def test_build_selection_excludes_ignored():
    gold = _mock_pool()
    sel = build_selection("nichtlinear", gold=gold)
    ids = [d["snippet_id"] for d in sel]
    assert ids, "selection must be non-empty"
    assert not any(sid.endswith("i") for sid in ids)
    assert all(d["type"] != "ignored" for d in sel)


def test_build_selection_size_constraints():
    gold = _mock_pool()
    sel = build_selection("nichtlinear", gold=gold)
    assert 20 <= len(sel) <= 30


@pytest.mark.skipif(
    not (CORPUS_ROOT / "nichtlinear" / CORPUS_FILES["nichtlinear"]).is_file(),
    reason="nichtlinear corpus is gitignored; skip smoke test in CI/no-corpus runs",
)
def test_smoke_real_corpus_nichtlinear():
    sel = build_selection("nichtlinear")
    assert len(sel) >= 20
    assert all(not d["snippet_id"].endswith("i") for d in sel)
    types = {d["type"] for d in sel}
    assert len(types) >= 2
