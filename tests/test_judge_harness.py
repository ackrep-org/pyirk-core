"""Tests for ``experiments.fnl_vs_direct.judge_harness``.

Strictly tokenfree: all judge calls go through the deterministic
:class:`MockJudgeClient`. :class:`OpusJudgeClient` is only instantiated
and probed for the no-API-key error path; it is never invoked end-to-end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from experiments.fnl_vs_direct.judge_harness import (
    MockJudgeClient,
    OpusJudgeClient,
    JudgeRequest,
    JudgeResult,
    build_prompt,
    judge_all,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXT = PROJECT_ROOT / "tests" / "fixtures" / "judge_harness"


def _read(name: str) -> str:
    return (FIXT / name).read_text(encoding="utf-8")


def _req_corpus_a(direct_text: str, snippet_id: str = "4") -> JudgeRequest:
    return JudgeRequest(
        snippet_id=snippet_id,
        corpus="nichtlinear",
        latex_source=_read("latex_snippet.tex"),
        fnl_gold=_read("fnl_gold.md"),
        pyirk_gold_block=_read("pyirk_gold.py"),
        direct_pyirk=direct_text,
    )


def _req_corpus_b(direct_text: str, snippet_id: str = "4") -> JudgeRequest:
    return JudgeRequest(
        snippet_id=snippet_id,
        corpus="bernstein",
        latex_source=_read("latex_snippet.tex"),
        fnl_gold=_read("fnl_gold.md"),
        pyirk_gold_block=None,
        direct_pyirk=direct_text,
    )


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_corpus_a_contains_all_blocks():
    req = _req_corpus_a(_read("direct_equivalent.py"))
    prompt = build_prompt(req)
    # LaTeX source, FNL gold and pyirk gold all present.
    assert "Vektorraum" in prompt  # from latex
    assert "vector space" in prompt  # from fnl_gold
    assert 'R1__has_label="vector"' in prompt  # from pyirk_gold
    # direct comes after the gold blocks.
    assert "Candidate direct-pyirk encoding:" in prompt
    # Order: latex -> fnl -> pyirk-gold -> direct.
    i_latex = prompt.index("LaTeX source")
    i_fnl = prompt.index("Formalized natural-language gold")
    i_pyirk = prompt.index("Gold pyirk module")
    i_direct = prompt.index("Candidate direct-pyirk encoding")
    assert i_latex < i_fnl < i_pyirk < i_direct
    # corpus + snippet id echoed at top.
    assert "Snippet id: 4" in prompt
    assert "Corpus: nichtlinear" in prompt


def test_build_prompt_corpus_b_omits_pyirk_gold():
    req = _req_corpus_b(_read("direct_equivalent.py"))
    prompt = build_prompt(req)
    assert "Gold pyirk module" not in prompt
    # No empty block header / leftover placeholder remains.
    assert "{pyirk_gold_block}" not in prompt
    # FNL block is still present, and so is the direct block.
    assert "Formalized natural-language gold" in prompt
    assert "Candidate direct-pyirk encoding:" in prompt


# ---------------------------------------------------------------------------
# MockJudgeClient verdict rules
# ---------------------------------------------------------------------------


def test_mock_judge_returns_equivalent_for_identical():
    client = MockJudgeClient()
    text = _read("direct_equivalent.py")
    req = JudgeRequest(
        snippet_id="4",
        corpus="nichtlinear",
        latex_source="x",
        fnl_gold="anything",
        pyirk_gold_block=text,  # identical to direct
        direct_pyirk=text,
    )
    res = client.judge(req)
    assert res.verdict == "equivalent"
    assert res.confidence > 0.5
    assert res.snippet_id == "4"
    assert res.corpus == "nichtlinear"


def test_mock_judge_returns_equivalent_for_same_labels_different_keys():
    client = MockJudgeClient()
    res = client.judge(_req_corpus_a(_read("direct_equivalent.py")))
    # gold and direct share the same R1 labels but use different keys.
    assert res.verdict == "equivalent"


def test_mock_judge_returns_partial_for_small_diff():
    client = MockJudgeClient()
    res = client.judge(_req_corpus_a(_read("direct_partial.py")))
    assert res.verdict == "partial"
    # at least one diff entry must be reported.
    assert res.differences
    assert any("vector" in d for d in res.differences)


def test_mock_judge_returns_wrong_for_diverged():
    client = MockJudgeClient()
    res = client.judge(_req_corpus_a(_read("direct_wrong.py")))
    assert res.verdict == "wrong"
    assert len(res.differences) > 3


def test_mock_judge_is_deterministic():
    client = MockJudgeClient()
    req = _req_corpus_a(_read("direct_partial.py"))
    r1 = client.judge(req)
    r2 = client.judge(req)
    assert r1.to_dict() == r2.to_dict()


# ---------------------------------------------------------------------------
# judge_all: writing + resume
# ---------------------------------------------------------------------------


def test_judge_all_writes_jsonl_and_is_resumable(tmp_path: Path):
    client = MockJudgeClient()
    reqs = [
        _req_corpus_a(_read("direct_equivalent.py"), snippet_id="4"),
        _req_corpus_a(_read("direct_partial.py"), snippet_id="5"),
        _req_corpus_a(_read("direct_wrong.py"), snippet_id="6"),
    ]
    out = tmp_path / "judge.jsonl"

    produced1 = judge_all(client, reqs, out)
    assert len(produced1) == 3
    assert out.exists()

    lines1 = out.read_text(encoding="utf-8").splitlines()
    assert len(lines1) == 3
    records1 = [json.loads(l) for l in lines1]
    verdicts = {r["snippet_id"]: r["verdict"] for r in records1}
    assert verdicts == {"4": "equivalent", "5": "partial", "6": "wrong"}

    # second run: same requests + one new -> only the new one is produced
    extra = _req_corpus_a(_read("direct_equivalent.py"), snippet_id="7")
    produced2 = judge_all(client, list(reqs) + [extra], out)
    assert len(produced2) == 1
    assert produced2[0].snippet_id == "7"

    lines2 = out.read_text(encoding="utf-8").splitlines()
    assert len(lines2) == 4  # no duplicates
    keys = [(json.loads(l)["corpus"], json.loads(l)["snippet_id"]) for l in lines2]
    assert len(set(keys)) == 4

    # all verdicts must be in the allowed set
    for line in lines2:
        rec = json.loads(line)
        assert rec["verdict"] in {"equivalent", "partial", "wrong"}


# ---------------------------------------------------------------------------
# OpusJudgeClient: constructible, fails cleanly without API key
# ---------------------------------------------------------------------------


def test_opus_client_is_constructible_without_calling():
    client = OpusJudgeClient()
    assert client.model == "claude-opus-4-7"
    # Strip the key for the duration of the test.
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        req = _req_corpus_a(_read("direct_equivalent.py"))
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            client.judge(req)
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved


# ---------------------------------------------------------------------------
# Subprocess smoke: CLI with --client mock
# ---------------------------------------------------------------------------


def test_cli_mock_smoke(tmp_path: Path):
    # Build a tiny throwaway selection + direct dir so the smoke does not
    # depend on the gitignored gold trees.
    selection = {
        "version": 1,
        "corpora": {
            "nichtlinear": [
                {"snippet_id": "4", "type": "subclass", "fnl_excerpt": "vec"},
                {"snippet_id": "5", "type": "subclass", "fnl_excerpt": "vec partial"},
            ]
        },
    }
    sel_path = tmp_path / "selection.json"
    sel_path.write_text(json.dumps(selection), encoding="utf-8")

    direct_dir = tmp_path / "direct"
    direct_dir.mkdir()
    (direct_dir / "nichtlinear_4.py").write_text(_read("direct_equivalent.py"))
    (direct_dir / "nichtlinear_5.py").write_text(_read("direct_partial.py"))

    gold_fnl_dir = tmp_path / "fnl_gold"
    gold_fnl_dir.mkdir()
    # leave gold_fnl_dir empty -> harness falls back to entry["fnl_excerpt"]

    latex_dir = tmp_path / "latex"
    latex_dir.mkdir()

    out = tmp_path / "smoke.jsonl"

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "experiments.fnl_vs_direct.judge_harness",
            "--selection", str(sel_path),
            "--direct-dir", str(direct_dir),
            "--gold-fnl-dir", str(gold_fnl_dir),
            "--latex-dir", str(latex_dir),
            "--client", "mock",
            "--corpus", "nichtlinear",
            "--limit", "2",
            "--out", str(out),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    assert "JUDGE-HARNESS" in res.stdout
    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        rec = json.loads(line)
        assert rec["verdict"] in {"equivalent", "partial", "wrong"}
        assert rec["corpus"] == "nichtlinear"
