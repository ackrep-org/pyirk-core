"""Tokenfree tests for ``experiments.fnl_vs_direct.aggregate_results``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.fnl_vs_direct.aggregate_results import (
    DEFINITION_TYPE_GROUP,
    REQUIRED_TYPES,
    aggregate_group,
    build_aggregate,
    build_records,
    calibration,
    render_aggregate_md,
    render_spotcheck_md,
    select_spotcheck,
)


# ---------------------------------------------------------------------------
# Fixtures: hand-crafted in-memory data
# ---------------------------------------------------------------------------


def _selection_basic() -> dict:
    return {
        "version": 1,
        "corpora": {
            "nichtlinear": [
                {"snippet_id": "2", "type": "declaration"},
                {"snippet_id": "4", "type": "subclass"},
                {"snippet_id": "6", "type": "instance"},
            ],
            "bernstein": [
                {"snippet_id": "1", "type": "declaration"},
                {"snippet_id": "3", "type": "notation"},
                {"snippet_id": "5", "type": "definition_or"},
            ],
        },
    }


def _stats_basic() -> dict:
    return {
        ("nichtlinear", "2"): {
            "corpus": "nichtlinear",
            "snippet_id": "2",
            "ok": True,
            "events": [
                {"attempt": 1, "cost_usd": 0.04, "event": "ok"},
            ],
        },
        ("nichtlinear", "4"): {
            "corpus": "nichtlinear",
            "snippet_id": "4",
            "ok": True,
            "events": [
                {"attempt": 1, "cost_usd": 0.02, "event": "fork"},
                {"attempt": 2, "cost_usd": 0.03, "event": "ok"},
            ],
        },
        ("nichtlinear", "6"): {
            "corpus": "nichtlinear",
            "snippet_id": "6",
            "ok": False,
            "events": [
                {"attempt": 1, "cost_usd": 0.05, "event": "gave_up"},
            ],
        },
        ("bernstein", "1"): {
            "corpus": "bernstein",
            "snippet_id": "1",
            "ok": True,
            "events": [{"attempt": 1, "cost_usd": 0.06, "event": "ok"}],
        },
        ("bernstein", "3"): {
            "corpus": "bernstein",
            "snippet_id": "3",
            "ok": True,
            "events": [{"attempt": 1, "cost_usd": 0.07, "event": "ok"}],
        },
        ("bernstein", "5"): {
            "corpus": "bernstein",
            "snippet_id": "5",
            "ok": True,
            "events": [{"attempt": 1, "cost_usd": 0.05, "event": "ok"}],
        },
    }


def _judge_basic() -> dict:
    return {
        ("nichtlinear", "2"): {
            "corpus": "nichtlinear",
            "snippet_id": "2",
            "verdict": "equivalent",
            "confidence": 0.95,
            "reason": "matches",
        },
        ("nichtlinear", "4"): {
            "corpus": "nichtlinear",
            "snippet_id": "4",
            "verdict": "partial",
            "confidence": 0.7,
            "reason": "some diffs",
        },
        ("nichtlinear", "6"): {
            "corpus": "nichtlinear",
            "snippet_id": "6",
            "verdict": "wrong",
            "confidence": 0.9,
            "reason": "wrong",
        },
        ("bernstein", "1"): {
            "corpus": "bernstein",
            "snippet_id": "1",
            "verdict": "equivalent",
            "confidence": 0.4,
            "reason": "weak match",
        },
        ("bernstein", "3"): {
            "corpus": "bernstein",
            "snippet_id": "3",
            "verdict": "partial",
            "confidence": 0.6,
            "reason": "partial",
        },
        ("bernstein", "5"): {
            "corpus": "bernstein",
            "snippet_id": "5",
            "verdict": "wrong",
            "confidence": 0.3,
            "reason": "missing",
        },
    }


def _struct_diff_basic() -> dict:
    # 2 -> clean ; 4 -> dirty (matches judge "partial"); 6 -> dirty (judge "wrong")
    return {
        "2": {
            "snippet_id": "2",
            "missing_items": [],
            "extra_items": [],
            "mismatched_relations": [],
            "missing_relations": [],
            "extra_relations": [],
            "score": 1.0,
        },
        "4": {
            "snippet_id": "4",
            "missing_items": ["foo"],
            "extra_items": [],
            "mismatched_relations": [],
            "missing_relations": [],
            "extra_relations": [],
            "score": 0.7,
        },
        "6": {
            "snippet_id": "6",
            "missing_items": ["bar"],
            "extra_items": ["baz"],
            "mismatched_relations": [],
            "missing_relations": [],
            "extra_relations": [],
            "score": 0.4,
        },
    }


# ---------------------------------------------------------------------------
# 1) Per-type aggregation: valid rate
# ---------------------------------------------------------------------------


def test_per_type_aggregation_valid_rate():
    # 3 records of type "declaration": 2 valid, 1 invalid.
    records = [
        {"corpus": "X", "snippet_id": "1", "type": "declaration", "valid": True,
         "structural_diff_empty": None, "judge_verdict": "equivalent",
         "judge_confidence": 0.9, "judge_reason": "", "attempts": 1,
         "cost_usd": 0.01},
        {"corpus": "X", "snippet_id": "2", "type": "declaration", "valid": True,
         "structural_diff_empty": None, "judge_verdict": "partial",
         "judge_confidence": 0.5, "judge_reason": "", "attempts": 1,
         "cost_usd": 0.02},
        {"corpus": "X", "snippet_id": "3", "type": "declaration", "valid": False,
         "structural_diff_empty": None, "judge_verdict": "wrong",
         "judge_confidence": 0.5, "judge_reason": "", "attempts": 2,
         "cost_usd": 0.04},
    ]
    g = aggregate_group(records)
    assert g["n"] == 3
    assert g["n_valid"] == 2
    assert g["judge_verdicts"] == {"equivalent": 1, "partial": 1, "wrong": 1}
    assert g["mean_cost_usd"] == pytest.approx((0.01 + 0.02 + 0.04) / 3.0)


# ---------------------------------------------------------------------------
# 2) Calibration: agreement count
# ---------------------------------------------------------------------------


def test_calibration_agreement_count():
    records = build_records(
        selection=_selection_basic(),
        stats=_stats_basic(),
        judge=_judge_basic(),
        struct_diff=_struct_diff_basic(),
    )
    cal = calibration(records)
    # corpus A has 3 snippets with structural diff entries.
    assert cal["n_corpus_A"] == 3
    # snippet 2: clean + judge "equivalent" -> agree.
    # snippet 4: dirty + judge "partial"   -> agree (both "non-empty/non-equivalent").
    # snippet 6: dirty + judge "wrong"     -> agree.
    assert cal["n_agreement"] == 3
    assert cal["n_divergence"] == 0


def test_calibration_divergence_when_judge_is_lenient():
    # Force a divergence: structural shows dirty on snippet 4 but judge says equivalent.
    judge = _judge_basic()
    judge[("nichtlinear", "4")] = dict(judge[("nichtlinear", "4")])
    judge[("nichtlinear", "4")]["verdict"] = "equivalent"
    records = build_records(
        selection=_selection_basic(),
        stats=_stats_basic(),
        judge=judge,
        struct_diff=_struct_diff_basic(),
    )
    cal = calibration(records)
    assert cal["n_divergence"] == 1
    assert cal["divergence_list"][0]["snippet_id"] == "4"
    assert cal["divergence_list"][0]["structural_clean"] is False
    assert cal["divergence_list"][0]["judge_verdict"] == "equivalent"


# ---------------------------------------------------------------------------
# 3) Calibration list schema/ordering
# ---------------------------------------------------------------------------


def test_calibration_divergence_list_format():
    judge = _judge_basic()
    # Mark snippet 4 and 6 as divergent in different directions.
    judge[("nichtlinear", "4")] = dict(judge[("nichtlinear", "4")])
    judge[("nichtlinear", "4")]["verdict"] = "equivalent"  # dirty / equivalent
    judge[("nichtlinear", "6")] = dict(judge[("nichtlinear", "6")])
    judge[("nichtlinear", "6")]["verdict"] = "equivalent"  # dirty / equivalent
    records = build_records(
        selection=_selection_basic(),
        stats=_stats_basic(),
        judge=judge,
        struct_diff=_struct_diff_basic(),
    )
    cal = calibration(records)
    # Sorted by snippet id (numeric).
    ids = [d["snippet_id"] for d in cal["divergence_list"]]
    assert ids == ["4", "6"]
    expected_keys = {"snippet_id", "structural_clean", "judge_verdict", "note"}
    for d in cal["divergence_list"]:
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 4) Spotcheck must include required types and at least 3 from each corpus.
# ---------------------------------------------------------------------------


def test_spotcheck_selection_includes_required_types():
    # 12 snippets covering every required type, mixed across two corpora.
    selection = {
        "version": 1,
        "corpora": {
            "nichtlinear": [
                {"snippet_id": "1", "type": "declaration"},
                {"snippet_id": "2", "type": "subclass"},
                {"snippet_id": "3", "type": "qualified"},
                {"snippet_id": "4", "type": "equivalence"},
                {"snippet_id": "5", "type": "definition_and"},
                {"snippet_id": "6", "type": "instance"},
            ],
            "bernstein": [
                {"snippet_id": "10", "type": "notation"},
                {"snippet_id": "11", "type": "declaration"},
                {"snippet_id": "12", "type": "instance"},
                {"snippet_id": "13", "type": "subclass"},
                {"snippet_id": "14", "type": "definition_or"},
                {"snippet_id": "15", "type": "notation"},
            ],
        },
    }
    stats = {
        (c, e["snippet_id"]): {
            "corpus": c,
            "snippet_id": e["snippet_id"],
            "ok": True,
            "events": [{"attempt": 1, "cost_usd": 0.02, "event": "ok"}],
        }
        for c, entries in selection["corpora"].items()
        for e in entries
    }
    judge = {
        (c, e["snippet_id"]): {
            "corpus": c,
            "snippet_id": e["snippet_id"],
            "verdict": "partial",
            "confidence": 0.5,
            "reason": "",
        }
        for c, entries in selection["corpora"].items()
        for e in entries
    }
    struct_diff = {
        e["snippet_id"]: {
            "snippet_id": e["snippet_id"],
            "missing_items": ["x"],
            "extra_items": [],
            "mismatched_relations": [],
            "missing_relations": [],
            "extra_relations": [],
            "score": 0.5,
        }
        for e in selection["corpora"]["nichtlinear"]
    }
    records = build_records(
        selection=selection,
        stats=stats,
        judge=judge,
        struct_diff=struct_diff,
    )
    selected = select_spotcheck(records, target_count=10, min_per_corpus=3)
    assert 8 <= len(selected) <= 10
    types_present = {r["type"] for r in selected}
    for required in REQUIRED_TYPES:
        assert required in types_present, f"missing required type: {required}"
    # Definition group: at least one of definition_and/definition_or.
    assert types_present & DEFINITION_TYPE_GROUP
    # At least 3 from each corpus.
    by_corpus = {"nichtlinear": 0, "bernstein": 0}
    for r in selected:
        by_corpus[r["corpus"]] += 1
    assert by_corpus["nichtlinear"] >= 3
    assert by_corpus["bernstein"] >= 3


# ---------------------------------------------------------------------------
# 5) Corpus B records carry no structural_diff_empty.
# ---------------------------------------------------------------------------


def test_corpus_b_has_no_structural_diff():
    records = build_records(
        selection=_selection_basic(),
        stats=_stats_basic(),
        judge=_judge_basic(),
        struct_diff=_struct_diff_basic(),
    )
    for r in records:
        if r["corpus"] == "bernstein":
            assert r["structural_diff_empty"] is None
        else:
            assert isinstance(r["structural_diff_empty"], bool)


# ---------------------------------------------------------------------------
# Extra: rendering does not crash on a realistic aggregate.
# ---------------------------------------------------------------------------


def test_render_aggregate_md_contains_required_sections():
    records = build_records(
        selection=_selection_basic(),
        stats=_stats_basic(),
        judge=_judge_basic(),
        struct_diff=_struct_diff_basic(),
    )
    agg = build_aggregate(records)
    md = render_aggregate_md(agg)
    assert "## Per Statement Type" in md
    assert "## Per Corpus Summary" in md
    assert "Calibration" in md
    # Two corpora should appear in the per-corpus table.
    assert "nichtlinear" in md
    assert "bernstein" in md


def test_render_spotcheck_md_falls_back_on_missing_sources():
    records = build_records(
        selection=_selection_basic(),
        stats=_stats_basic(),
        judge=_judge_basic(),
        struct_diff=_struct_diff_basic(),
    )
    selected = records  # render everything
    md = render_spotcheck_md(
        selected,
        latex_sources={"nichtlinear": "", "bernstein": ""},
        fnl_sources={"nichtlinear": "", "bernstein": ""},
        direct_sources={"nichtlinear": "", "bernstein": ""},
        struct_diff=_struct_diff_basic(),
    )
    assert "spotcheck" in md.lower()
    for rec in selected:
        assert f"Snippet {rec['corpus']}/{rec['snippet_id']}" in md
        # falls back gracefully to (unavailable) markers.
        assert "(unavailable)" in md
