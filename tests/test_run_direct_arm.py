"""Tokenfree smoke tests for ``experiments.fnl_vs_direct.run_direct_arm``.

These tests exercise the two non-LLM-dependent pieces of the direct-arm
runner: the monkey-patch that injects the Opus model id into substrate
``propose_via_claude`` calls, and the resume helper that filters out
snippets already recorded in ``stats.jsonl``.

No tokens are spent: ``subprocess.run`` is replaced with a recorder that
returns a synthetic CLI-shaped envelope.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest


# Make experiments/ importable as a top-level package when running the test.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from experiments.fnl_vs_direct import run_direct_arm  # noqa: E402
import pyirk  # noqa: E402
from pyirk import authoring as _substrate  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_propose_via_claude():
    """Each test gets a clean substrate.propose_via_claude pointer."""
    saved = _substrate.propose_via_claude
    yield
    _substrate.propose_via_claude = saved


@pytest.fixture
def _restore_validate_module():
    """Save/restore the substrate.validate_module pointer for patch tests."""
    saved = _substrate.validate_module
    yield
    _substrate.validate_module = saved


def _fake_completed_process(stdout: str = '{"result": "OK", "total_cost_usd": 0.0}'):
    cp = mock.Mock()
    cp.returncode = 0
    cp.stdout = stdout
    cp.stderr = ""
    return cp


def test_apply_opus_patch_injects_model_into_cli_args():
    run_direct_arm.apply_opus_patch("claude-opus-4-7")

    with mock.patch("pyirk.authoring.subprocess.run") as run_mock:
        run_mock.return_value = _fake_completed_process()
        _substrate.propose_via_claude("hi")

    assert run_mock.call_count == 1
    args, _kwargs = run_mock.call_args
    cmd = args[0]
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-4-7"


def test_apply_opus_patch_respects_explicit_caller_model():
    """An explicit ``model=`` from the caller must NOT be overridden."""
    run_direct_arm.apply_opus_patch("claude-opus-4-7")

    with mock.patch("pyirk.authoring.subprocess.run") as run_mock:
        run_mock.return_value = _fake_completed_process()
        _substrate.propose_via_claude("hi", model="sonnet")

    cmd = run_mock.call_args.args[0]
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_apply_opus_patch_is_idempotent():
    """Repeat calls update the model id without stacking wrappers."""
    original = _substrate.propose_via_claude
    run_direct_arm.apply_opus_patch("claude-opus-4-7")
    once = _substrate.propose_via_claude
    run_direct_arm.apply_opus_patch("claude-opus-4-8")
    twice = _substrate.propose_via_claude

    # both wrappers share the SAME original underneath
    assert getattr(once, "__opus_orig__") is original
    assert getattr(twice, "__opus_orig__") is original
    assert getattr(twice, "__opus_model__") == "claude-opus-4-8"

    with mock.patch("pyirk.authoring.subprocess.run") as run_mock:
        run_mock.return_value = _fake_completed_process()
        _substrate.propose_via_claude("hi")
    cmd = run_mock.call_args.args[0]
    assert cmd[cmd.index("--model") + 1] == "claude-opus-4-8"


def test_load_already_done_skips_missing_file(tmp_path: Path):
    assert run_direct_arm.load_already_done(tmp_path / "missing.jsonl") == set()


def test_load_already_done_reads_completed_pairs(tmp_path: Path):
    stats = tmp_path / "stats.jsonl"
    stats.write_text(
        json.dumps({"corpus": "nichtlinear", "snippet_id": "2", "ok": True, "events": []}) + "\n"
        + json.dumps({"corpus": "nichtlinear", "snippet_id": "4", "ok": False, "events": []}) + "\n"
        + json.dumps({"corpus": "bernstein", "snippet_id": "1", "ok": True, "events": []}) + "\n"
        # blank line + corrupt trailing line should be tolerated
        + "\n"
        + "{not-json"
    )
    done = run_direct_arm.load_already_done(stats)
    assert done == {
        ("nichtlinear", "2"),
        ("nichtlinear", "4"),
        ("bernstein", "1"),
    }


def test_apply_validate_prefix_patch_clears_stale_prefix(
    monkeypatch, _restore_validate_module
):
    """The wrapper must release a stale ``_validate`` prefix BEFORE delegating
    to the original validator so a different module path can be validated
    without ``InvalidPrefixError``."""
    called_with = []

    def fake_original(path):
        # by the time the original runs, the stale prefix must be gone
        assert run_direct_arm._VALIDATE_PREFIX not in pyirk.ds.uri_prefix_mapping.b
        called_with.append(path)
        return (True, "")

    monkeypatch.setattr(_substrate, "validate_module", fake_original)
    run_direct_arm.apply_validate_prefix_patch()

    stale_uri = "irk:/test_validate_prefix_patch_stale"
    pyirk.ds.uri_prefix_mapping.add_pair(stale_uri, run_direct_arm._VALIDATE_PREFIX)

    unloaded = []

    def fake_unload(uri, strict=True):
        unloaded.append(uri)
        pyirk.ds.uri_prefix_mapping.remove_pair(key_a=uri, strict=False)

    monkeypatch.setattr(pyirk, "unload_mod", fake_unload)

    try:
        result = _substrate.validate_module(Path("/nonexistent_module.py"))
    finally:
        # safety net: if the wrapper didn't clean up (test failure path),
        # we still leave the substrate's mapping pristine for the next test.
        pyirk.ds.uri_prefix_mapping.remove_pair(
            key_b=run_direct_arm._VALIDATE_PREFIX, strict=False
        )

    assert result == (True, "")
    assert unloaded == [stale_uri]
    assert called_with == [Path("/nonexistent_module.py")]


def test_apply_validate_prefix_patch_is_idempotent(_restore_validate_module):
    """Calling the patch twice keeps the wrapper a single layer deep."""
    run_direct_arm.apply_validate_prefix_patch()
    once = _substrate.validate_module
    run_direct_arm.apply_validate_prefix_patch()
    twice = _substrate.validate_module
    assert once is twice
    assert getattr(twice, "__validate_patched__", False) is True


def test_collect_planned_sorts_natural_and_applies_limit_per_corpus():
    selection = {
        "corpora": {
            "nichtlinear": [
                {"snippet_id": "10", "type": "subclass"},
                {"snippet_id": "2", "type": "declaration"},
                {"snippet_id": "17i", "type": "qualified"},
                {"snippet_id": "4", "type": "instance"},
            ],
            "bernstein": [
                {"snippet_id": "1", "type": "declaration"},
                {"snippet_id": "3", "type": "declaration"},
            ],
        }
    }
    planned = run_direct_arm.collect_planned(
        selection, corpora=["nichtlinear", "bernstein"], limit=2
    )
    # natural sort within each corpus, then 2 per corpus
    assert planned == [
        ("nichtlinear", "2", "declaration"),
        ("nichtlinear", "4", "instance"),
        ("bernstein", "1", "declaration"),
        ("bernstein", "3", "declaration"),
    ]
