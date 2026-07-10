"""Tests for the math-tuned prompt header in ``pyirk.authoring.latex``.

These tests are tokenfree: no real LLM calls. They check that
``LATEX_PROMPT_HEADER`` carries the expected markers and that the adapter
swaps it into the substrate's prompt builder for the duration of a snippet
import call.
"""

from __future__ import annotations

from pathlib import Path

import pyirk.authoring as substrate
from pyirk.authoring.latex import (
    LATEX_PROMPT_HEADER,
    LatexSnippet,
    _swap_prompt_header,
    import_snippet,
)


def test_latex_prompt_header_contains_expected_markers():
    """The math-tuned header advertises the idioms math snippets need."""
    h = LATEX_PROMPT_HEADER
    # Worked-example labels from the canonical block.
    assert 'R1__has_label="bounded set"' in h
    assert 'R1__has_label="set intersection"' in h
    assert 'R1__has_label="empty set"' in h
    # Reuse of the builtin set class.
    assert 'p.I13["mathematical set"]' in h
    # The R24 LaTeX-notation pattern with positional placeholders.
    assert "R24__has_LaTeX_string" in h
    assert "arg1" in h and "arg2" in h
    # Domain/range relations are demonstrated.
    assert "R8__has_domain_of_argument_1" in h
    assert "R11__has_range_of_result" in h
    # Arity guidance for operators (the I7/I8/I9 family).
    assert 'p.I8["mathematical operation with arity 2"]' in h
    # Iff/implication pattern is still available for proposition snippets.
    assert "I17" in h and "I15" in h
    # Same bootstrap warning as the Lean header (do not redeclare module setup).
    assert "start_mod" in h and "end_mod" in h


def test_latex_prompt_header_differs_from_substrate_header():
    """``LATEX_PROMPT_HEADER`` is a genuine replacement, not a copy."""
    assert LATEX_PROMPT_HEADER != substrate.PROMPT_HEADER
    # The Lean worked example must NOT leak into the math header.
    assert "Pythagorean theorem" not in LATEX_PROMPT_HEADER
    assert "planar triangle" not in LATEX_PROMPT_HEADER


def test_swap_prompt_header_is_scoped_and_restored():
    """The context manager swaps and restores the substrate constant."""
    original = substrate.PROMPT_HEADER
    sentinel = "SENTINEL HEADER"
    with _swap_prompt_header(sentinel):
        assert substrate.PROMPT_HEADER == sentinel
    assert substrate.PROMPT_HEADER == original


def test_swap_prompt_header_restores_on_exception():
    """Restoration happens even if the inner block raises."""
    original = substrate.PROMPT_HEADER
    try:
        with _swap_prompt_header("OTHER"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert substrate.PROMPT_HEADER == original


def test_import_snippet_uses_math_header_in_substrate_prompt(monkeypatch, tmp_path):
    """``import_snippet`` makes ``LATEX_PROMPT_HEADER`` visible to
    ``build_import_prompt`` for the duration of the substrate call.

    The substrate is patched so the prompt builder records the header it
    sees, without ever calling Claude or touching the working module.
    """
    seen = {}

    def fake_build(*, theorem_text, source_info, retrieval_hits, dependency_index,
                   working_summary, working_module_uri, loaded_prefixes,
                   extra_context=""):
        # Record the PROMPT_HEADER visible to the substrate at this moment.
        seen["header"] = substrate.PROMPT_HEADER
        return "<prompt>"

    def fake_propose(prompt, timeout=600, model="sonnet"):
        return substrate.ClaudeCallResult(text="OK:\n```python\npass\n```\n")

    # Stub away the parts of the loop that would touch the filesystem / LLM.
    monkeypatch.setattr(substrate, "build_import_prompt", fake_build)
    monkeypatch.setattr(substrate, "propose_via_claude", fake_propose)
    monkeypatch.setattr(substrate, "summarize_module", lambda p, max_items=50: "")
    monkeypatch.setattr(substrate, "extract_module_uri", lambda p: "irk:/test/v1")
    monkeypatch.setattr(substrate, "_collect_occupied_keys", lambda p: set())
    monkeypatch.setattr(substrate, "append_to_module", lambda p, code: None)
    monkeypatch.setattr(substrate, "validate_module", lambda p: (True, ""))

    session = substrate.Session()
    snippet = LatexSnippet(snippet_id="42", text="Sei X eine Menge.", raw="\\snippet{42}\nSei X eine Menge.")

    # The working_module_path is never read because summarize_module / extract_module_uri
    # are stubbed -- a non-existent path is fine.
    wm = tmp_path / "wm.py"
    wm.write_text("# placeholder\np.end_mod()\n")

    ok = import_snippet(
        snippet,
        session,
        working_module_path=wm,
        source_url="local://test",
        ask_user=lambda q, opts: opts[0][0] if opts else "a",
    )
    assert ok is True
    assert seen["header"] == LATEX_PROMPT_HEADER
    # And after the call, the substrate has its Lean-tuned header back.
    assert substrate.PROMPT_HEADER != LATEX_PROMPT_HEADER


def test_substrate_header_unchanged_after_import_snippet(monkeypatch, tmp_path):
    """Regression: a fresh import does NOT leak the math header globally.

    Other adapters (e.g. ``pyirk.authoring.lean``) must keep seeing the
    Lean-tuned header after ``import_snippet`` returns -- including when the
    substrate call fails / gives up.
    """
    original = substrate.PROMPT_HEADER

    def fake_build(**kwargs):
        return "<prompt>"

    def fake_propose(prompt, timeout=600, model="sonnet"):
        # Malformed response -> exhausts attempts -> import_one_statement gives up.
        return substrate.ClaudeCallResult(text="not a valid response")

    monkeypatch.setattr(substrate, "build_import_prompt", fake_build)
    monkeypatch.setattr(substrate, "propose_via_claude", fake_propose)
    monkeypatch.setattr(substrate, "summarize_module", lambda p, max_items=50: "")
    monkeypatch.setattr(substrate, "extract_module_uri", lambda p: "irk:/test/v1")

    session = substrate.Session()
    snippet = LatexSnippet(snippet_id="1", text="body", raw="\\snippet{1}\nbody")
    wm = tmp_path / "wm.py"
    wm.write_text("# placeholder\np.end_mod()\n")

    import_snippet(
        snippet,
        session,
        working_module_path=wm,
        ask_user=lambda q, opts: "a",
    )
    assert substrate.PROMPT_HEADER == original
