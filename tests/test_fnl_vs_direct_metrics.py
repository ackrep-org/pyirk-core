"""Tests for ``experiments.fnl_vs_direct.metrics`` and the mock dry-run harness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from experiments.fnl_vs_direct.metrics import (
    aggregate_events,
    summarize_by_corpus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_NICHTLINEAR = (
    PROJECT_ROOT
    / "experiments"
    / "fnl_vs_direct"
    / "corpus_gold__gitignore__"
    / "nichtlinear"
    / "kapitel2.tex"
)


# ---------------------------------------------------------------------------
# aggregate_events


def test_aggregate_events_empty_input():
    out = aggregate_events([])
    assert out["n_snippets"] == 0
    assert out["ok_count"] == 0
    assert out["validity_rate"] == 0.0
    assert out["fork_rate"] == 0.0
    assert out["retry_rate"] == 0.0
    assert out["per_type_validity"] == {}
    assert out["per_snippet"] == []


def test_aggregate_events_only_ok():
    records = [
        {
            "snippet_id": "1",
            "corpus": "x",
            "type": "notation",
            "outcome": "ok",
            "events": [{"event": "ok", "attempt": 1}],
        },
        {
            "snippet_id": "2",
            "corpus": "x",
            "type": "subclass",
            "outcome": "ok",
            "events": [{"event": "ok", "attempt": 1}],
        },
    ]
    out = aggregate_events(records)
    assert out["n_snippets"] == 2
    assert out["ok_count"] == 2
    assert out["validity_rate"] == 1.0
    assert out["fork_rate"] == 0.0
    assert out["retry_rate"] == 0.0
    assert out["validation_fail_count"] == 0
    assert out["timeout_count"] == 0
    assert out["nonascii_count"] == 0
    assert out["fork_count"] == 0
    assert out["per_type_validity"]["notation"] == 1.0
    assert out["per_type_validity"]["subclass"] == 1.0


def test_aggregate_events_mixed_outcomes_and_per_type():
    records = [
        {
            "snippet_id": "1",
            "corpus": "x",
            "type": "notation",
            "outcome": "ok",
            "events": [{"event": "ok", "attempt": 1}],
        },
        {
            "snippet_id": "2",
            "corpus": "x",
            "type": "subclass",
            "outcome": "ok",
            "events": [
                {"event": "validation_fail", "attempt": 1, "error": "boom"},
                {"event": "ok", "attempt": 2},
            ],
        },
        {
            "snippet_id": "3",
            "corpus": "x",
            "type": "qualified",
            "outcome": "failed",
            "events": [
                {
                    "event": "fork",
                    "attempt": 1,
                    "question": "q",
                    "options": [],
                    "choice": "a",
                },
                {"event": "validation_fail", "attempt": 2, "error": "x"},
                {"event": "gave_up", "attempts": 2},
            ],
        },
        {
            "snippet_id": "4",
            "corpus": "x",
            "type": "notation",
            "outcome": "failed",
            "events": [
                {"event": "timeout", "attempt": 1, "timeout_s": 600},
                {"event": "gave_up", "attempts": 1},
            ],
        },
    ]
    out = aggregate_events(records)
    assert out["n_snippets"] == 4
    assert out["ok_count"] == 2
    assert out["validity_rate"] == pytest.approx(0.5)
    assert out["validation_fail_count"] == 2
    assert out["fork_count"] == 1
    assert out["fork_rate"] == pytest.approx(0.25)
    # snippet 2 retried after a validation_fail, snippet 3 retried after fork+fail,
    # snippet 4 has only one attempt with no validation_fail -> not a retry
    assert out["retry_rate"] == pytest.approx(0.5)
    assert out["timeout_count"] == 1
    # per-type validity:
    # notation has 2 records, 1 ok -> 0.5
    # subclass has 1 record, 1 ok -> 1.0
    # qualified has 1 record, 0 ok -> 0.0
    assert out["per_type_validity"]["notation"] == 0.5
    assert out["per_type_validity"]["subclass"] == 1.0
    assert out["per_type_validity"]["qualified"] == 0.0
    assert out["per_type_counts"] == {"notation": 2, "subclass": 1, "qualified": 1}


def test_aggregate_events_unknown_event_type_does_not_invent():
    records = [
        {
            "snippet_id": "1",
            "corpus": "x",
            "type": "notation",
            "outcome": "ok",
            "events": [{"event": "ok", "attempt": 1}],
        }
    ]
    out = aggregate_events(records)
    # event types not present in records remain at zero / empty -- not invented
    assert out["nonascii_count"] == 0
    assert out["timeout_count"] == 0
    assert out["fork_count"] == 0


# ---------------------------------------------------------------------------
# summarize_by_corpus


def test_summarize_by_corpus_splits_records_per_corpus():
    selection = {"corpora": {"A": [], "B": []}}
    records = [
        {
            "snippet_id": "1",
            "corpus": "A",
            "type": "notation",
            "outcome": "ok",
            "events": [{"event": "ok", "attempt": 1}],
        },
        {
            "snippet_id": "2",
            "corpus": "B",
            "type": "subclass",
            "outcome": "ok",
            "events": [{"event": "ok", "attempt": 1}],
        },
        {
            "snippet_id": "3",
            "corpus": "B",
            "type": "subclass",
            "outcome": "failed",
            "events": [
                {"event": "validation_fail", "attempt": 1, "error": "x"},
                {"event": "gave_up", "attempts": 1},
            ],
        },
    ]
    out = summarize_by_corpus(records, selection)
    assert set(out.keys()) == {"A", "B"}
    assert out["A"]["n_snippets"] == 1
    assert out["A"]["validity_rate"] == 1.0
    assert out["B"]["n_snippets"] == 2
    assert out["B"]["validity_rate"] == 0.5
    assert out["B"]["validation_fail_count"] == 1


def test_summarize_by_corpus_empty_corpus_still_in_output():
    selection = {"corpora": {"A": [], "B": []}}
    records = [
        {
            "snippet_id": "1",
            "corpus": "A",
            "type": "notation",
            "outcome": "ok",
            "events": [{"event": "ok", "attempt": 1}],
        }
    ]
    out = summarize_by_corpus(records, selection)
    assert out["B"]["n_snippets"] == 0
    assert out["B"]["validity_rate"] == 0.0


# ---------------------------------------------------------------------------
# Mock-dry-run harness smoke + determinism


def _run_harness(out_dir: Path, args: list[str]):
    cmd = [
        sys.executable,
        "-m",
        "experiments.fnl_vs_direct.latex_bulk_dry_run",
        "--out-dir",
        str(out_dir),
        *args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )


def test_dry_run_smoke_nichtlinear_limit_4(tmp_path):
    if not CORPUS_NICHTLINEAR.exists():
        pytest.skip(f"corpus file missing: {CORPUS_NICHTLINEAR}")
    out_dir = tmp_path / "out"
    proc = _run_harness(out_dir, ["--limit", "4", "--corpus", "nichtlinear"])
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    stats_path = out_dir / "stats.jsonl"
    summary_path = out_dir / "summary.json"
    assert stats_path.exists()
    assert summary_path.exists()
    lines = [ln for ln in stats_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 4, f"expected 4 records, got {len(lines)}"
    parsed = [json.loads(ln) for ln in lines]
    for rec in parsed:
        assert "snippet_id" in rec
        assert "corpus" in rec and rec["corpus"] == "nichtlinear"
        assert "type" in rec
        assert "events" in rec
        assert "outcome" in rec
    summary = json.loads(summary_path.read_text())
    assert "aggregate" in summary
    assert "by_corpus" in summary
    assert "n_records" in summary
    assert "corpora_processed" in summary
    assert summary["aggregate"]["n_snippets"] == 4


def test_dry_run_deterministic_byte_identical(tmp_path):
    if not CORPUS_NICHTLINEAR.exists():
        pytest.skip(f"corpus file missing: {CORPUS_NICHTLINEAR}")
    a = tmp_path / "a"
    b = tmp_path / "b"
    proc_a = _run_harness(a, ["--limit", "6", "--corpus", "nichtlinear"])
    proc_b = _run_harness(b, ["--limit", "6", "--corpus", "nichtlinear"])
    assert proc_a.returncode == 0, proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stderr
    stats_a = (a / "stats.jsonl").read_bytes()
    stats_b = (b / "stats.jsonl").read_bytes()
    assert stats_a == stats_b, "stats.jsonl is not byte-identical across runs"


def test_dry_run_default_fail_path_exercised(tmp_path):
    if not CORPUS_NICHTLINEAR.exists():
        pytest.skip(f"corpus file missing: {CORPUS_NICHTLINEAR}")
    out_dir = tmp_path / "out"
    # snippet '2' is the first sorted nichtlinear ID and is in DEFAULT_FAIL_SNIPPETS,
    # so a --limit that includes it must produce a validation_fail event.
    proc = _run_harness(out_dir, ["--limit", "4", "--corpus", "nichtlinear"])
    assert proc.returncode == 0, proc.stderr
    summary = json.loads((out_dir / "summary.json").read_text())
    assert summary["aggregate"]["validation_fail_count"] >= 1
    assert summary["aggregate"]["retry_rate"] > 0.0
