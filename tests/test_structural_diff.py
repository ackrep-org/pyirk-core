"""Tests for ``experiments.fnl_vs_direct.structural_diff``.

Focus: AST parsing (declarations, update_relations, set_relation, snippet
bucketing, ignored markers, prelude) and the reuse-tolerant label-keyed
multiset diff (identical / reuse / diverged / ignored cases) plus an
optional smoke run against the gitignored gold module.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from experiments.fnl_vs_direct.structural_diff import (
    ItemRec,
    ModuleSummary,
    RelRec,
    SnippetBlock,
    SnippetDiff,
    diff_modules,
    diff_snippet,
    parse_pyirk_module,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXT = PROJECT_ROOT / "tests" / "fixtures" / "structural_diff"


def _read(name: str) -> str:
    return (FIXT / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_pyirk_module


def test_parse_gold_mini_prelude_and_buckets():
    summary = parse_pyirk_module(_read("gold_mini.py"))
    # Prelude: I100 ("snippet") and R200 ("contains concept").
    prelude_item_labels = [r.label for r in summary.prelude_items]
    assert "snippet" in prelude_item_labels
    prelude_rel_labels = [r.label for r in summary.prelude_relations]
    assert "contains concept" in prelude_rel_labels

    assert set(summary.by_snippet) == {"1", "2", "3"}
    s1 = summary.by_snippet["1"]
    assert [r.label for r in s1.items] == ["snippet(1)", "vector space"]
    # vector space had two R-keys merged from update_relations.
    vs = [r for r in s1.items if r.label == "vector space"][0]
    assert "R3" in vs.extra
    assert vs.extra["R3"] == "mathematical set"
    assert "R77" in vs.extra

    s2 = summary.by_snippet["2"]
    assert [r.label for r in s2.items] == ["snippet(2)", "linear mapping"]
    lm = [r for r in s2.items if r.label == "linear mapping"][0]
    assert lm.extra["R3"] == "vector space"


def test_parse_marker_item_belongs_to_own_snippet():
    summary = parse_pyirk_module(_read("gold_mini.py"))
    # The marker item itself sits in its bucket.
    s3 = summary.by_snippet["3"]
    marker_labels = [r.label for r in s3.items if r.label == "snippet(3)"]
    assert marker_labels == ["snippet(3)"]
    marker = [r for r in s3.items if r.label == "snippet(3)"][0]
    # update_relations on the marker is merged.
    assert marker.extra.get("R4") == "snippet"


def test_parse_ignored_snippet_is_separate_bucket():
    summary = parse_pyirk_module(_read("direct_with_ignored.py"))
    # "1i" must be its own bucket, distinct from "1".
    assert "1i" in summary.by_snippet
    assert "1" in summary.by_snippet
    s1i = summary.by_snippet["1i"]
    labels = [r.label for r in s1i.items]
    assert "snippet(1i)" in labels
    assert "experimental notion" in labels


# ---------------------------------------------------------------------------
# diff_snippet / diff_modules


def test_diff_identical_yields_score_one():
    g = parse_pyirk_module(_read("gold_mini.py"))
    d = parse_pyirk_module(_read("direct_identical.py"))
    diffs = diff_modules(g, d, ["1", "2", "3"])
    for sid, diff in diffs.items():
        assert diff.missing_items == [], f"{sid}: {diff.missing_items}"
        assert diff.extra_items == [], f"{sid}: {diff.extra_items}"
        assert diff.mismatched_relations == [], f"{sid}: {diff.mismatched_relations}"
        assert diff.missing_relations == [], f"{sid}: {diff.missing_relations}"
        assert diff.extra_relations == [], f"{sid}: {diff.extra_relations}"
        assert diff.score == 1.0, f"{sid}: {diff.score}"


def test_diff_reuse_with_reuse_index():
    g = parse_pyirk_module(_read("gold_mini.py"))
    d = parse_pyirk_module(_read("direct_reuse.py"))
    reuse_index = {"vector space": "ma.I5166"}
    diffs = diff_modules(g, d, ["1", "2", "3"], reuse_index=reuse_index)
    s1 = diffs["1"]
    assert s1.missing_items == [], s1.missing_items
    assert s1.extra_items == [], s1.extra_items
    # snippet(2)/(3) are unchanged structurally.
    assert diffs["2"].missing_items == []
    assert diffs["3"].missing_items == []


def test_diff_reuse_without_reuse_index_flags_missing():
    g = parse_pyirk_module(_read("gold_mini.py"))
    d = parse_pyirk_module(_read("direct_reuse.py"))
    diffs = diff_modules(g, d, ["1"])
    # No reuse_index passed -> the absent "vector space" must be flagged.
    assert "vector space" in diffs["1"].missing_items


def test_diff_diverged_reports_exactly_the_three_divergences():
    g = parse_pyirk_module(_read("gold_mini.py"))
    d = parse_pyirk_module(_read("direct_diverged.py"))
    diffs = diff_modules(g, d, ["1", "2", "3"])
    # snippet(1): vector space missing.
    assert "vector space" in diffs["1"].missing_items
    # snippet(2): affine mapping extra.
    assert "affine mapping" in diffs["2"].extra_items
    # snippet(3): R3 on "dual space" mismatched.
    mm = diffs["3"].mismatched_relations
    assert any(
        label == "dual space" and rkey == "R3"
        and gold_v == "vector space" and direct_v == "linear mapping"
        for (label, rkey, gold_v, direct_v) in mm
    ), mm
    # And the snippets that were not touched still score perfectly.
    # (snippet(1) lost 1 item + 1 extra; snippet(3) has 1 mismatch only.)
    assert diffs["1"].score < 1.0
    assert diffs["2"].score < 1.0
    assert diffs["3"].score < 1.0


def test_diff_with_ignored_skips_explicit_selection():
    g = parse_pyirk_module(_read("gold_mini.py"))
    d = parse_pyirk_module(_read("direct_with_ignored.py"))
    # Explicit selection of 1, 2, 3 must skip 1i entirely.
    diffs = diff_modules(g, d, ["1", "2", "3"])
    assert "1i" not in diffs
    # And the 1/2/3 diffs are clean (the ignored block does not bleed in).
    for sid in ("1", "2", "3"):
        assert diffs[sid].score == 1.0, (sid, diffs[sid])


def test_diff_score_clamped_to_zero_for_huge_divergence():
    # Construct a gold with one item and a direct with many extras.
    g = ModuleSummary(by_snippet={"1": SnippetBlock(
        snippet_id="1",
        items=[ItemRec(key="I1", label="x")],
    )})
    d = ModuleSummary(by_snippet={"1": SnippetBlock(
        snippet_id="1",
        items=[
            ItemRec(key="I1", label="a"),
            ItemRec(key="I2", label="b"),
            ItemRec(key="I3", label="c"),
            ItemRec(key="I4", label="d"),
            ItemRec(key="I5", label="e"),
        ],
    )})
    diff = diff_snippet(g.by_snippet["1"], d.by_snippet["1"])
    assert diff.score == 0.0


# ---------------------------------------------------------------------------
# CLI


def test_cli_runs_against_mini_fixtures(tmp_path):
    out = tmp_path / "out.json"
    cmd = [
        sys.executable,
        "-m",
        "experiments.fnl_vs_direct.structural_diff",
        "--gold",
        str(FIXT / "gold_mini.py"),
        "--direct",
        str(FIXT / "direct_identical.py"),
        "--snippets",
        "1,2,3",
        "--out",
        str(out),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), check=False
    )
    assert result.returncode == 0, result.stderr
    assert "STRUCTDIFF:" in result.stdout
    assert "total_score=1.0000" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload["diffs"]) == {"1", "2", "3"}
    for d in payload["diffs"].values():
        assert d["score"] == 1.0


# ---------------------------------------------------------------------------
# Smoke against real gold (skipped if missing)


GOLD_REAL = (
    PROJECT_ROOT
    / "experiments"
    / "fnl_vs_direct"
    / "corpus_gold__gitignore__"
    / "nichtlinear"
    / "pyirk_gold.py"
)
SELECTION = PROJECT_ROOT / "experiments" / "fnl_vs_direct" / "snippet_selection.json"


@pytest.mark.skipif(not GOLD_REAL.exists(), reason="pyirk_gold.py not present locally")
def test_self_diff_real_gold_is_perfect():
    src = GOLD_REAL.read_text(encoding="utf-8")
    g = parse_pyirk_module(src)
    d = parse_pyirk_module(src)
    sel = json.loads(SELECTION.read_text(encoding="utf-8"))
    sids = [str(e["snippet_id"]) for e in sel["corpora"]["nichtlinear"]]
    diffs = diff_modules(g, d, sids)
    # Self-diff is byte-identical -> every bucket must match perfectly.
    for sid, diff in diffs.items():
        assert diff.score == 1.0, (sid, diff)
