"""Tests for the LaTeX snippet adapter (``pyirk.authoring.latex``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyirk.authoring.latex import (
    LatexSnippet,
    find_snippet,
    parse_snippets,
)


def test_parse_snippets_basic_numeric_and_suffix():
    source = (
        "\\snippet{1}\n"
        "First body.\n"
        "\\snippet{2}\n"
        "Second body line 1.\nSecond body line 2.\n"
        "\\snippet{3i}\n"
        "Third body (ignored-style suffix).\n"
        "\\snippet{4}\n"
        "Fourth body.\n"
    )
    snippets = parse_snippets(source)
    assert len(snippets) == 4
    assert [s.snippet_id for s in snippets] == ["1", "2", "3i", "4"]
    assert snippets[0].text == "\nFirst body.\n"
    assert snippets[1].text == "\nSecond body line 1.\nSecond body line 2.\n"
    assert snippets[2].text == "\nThird body (ignored-style suffix).\n"
    assert snippets[3].text == "\nFourth body.\n"
    # raw includes the marker itself
    assert snippets[0].raw.startswith("\\snippet{1}")
    assert snippets[2].raw.startswith("\\snippet{3i}")


def test_parse_snippets_last_snippet_runs_to_eof():
    source = "\\snippet{1}\nbody one.\n\\snippet{42}\nlast body, no trailing marker."
    snippets = parse_snippets(source)
    assert len(snippets) == 2
    assert snippets[1].snippet_id == "42"
    assert snippets[1].text == "\nlast body, no trailing marker."
    assert snippets[1].raw.endswith("last body, no trailing marker.")


def test_parse_snippets_empty_string_yields_empty_list():
    assert parse_snippets("") == []


def test_parse_snippets_content_before_first_marker_is_discarded():
    source = "preamble that should be ignored\n\\snippet{1}\nbody.\n"
    snippets = parse_snippets(source)
    assert len(snippets) == 1
    assert snippets[0].snippet_id == "1"
    assert snippets[0].text == "\nbody.\n"


def test_find_snippet_hit_and_miss():
    snippets = [
        LatexSnippet(snippet_id="1", text="a", raw="\\snippet{1}a"),
        LatexSnippet(snippet_id="17i", text="b", raw="\\snippet{17i}b"),
    ]
    found = find_snippet(snippets, "17i")
    assert found is not None
    assert found.snippet_id == "17i"
    assert find_snippet(snippets, "999") is None
    assert find_snippet([], "1") is None


def test_parse_snippets_corpus_A_smoke():
    """Smoke test against the real Korpus A (kapitel2.tex, expected ~74 snippets).

    The corpus is git-ignored; skip cleanly if the file is absent on this host.
    """
    corpus = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "fnl_vs_direct"
        / "corpus_gold__gitignore__"
        / "nichtlinear"
        / "kapitel2.tex"
    )
    if not corpus.exists():
        pytest.skip(f"corpus file missing: {corpus}")
    source = corpus.read_text()
    snippets = parse_snippets(source)
    assert len(snippets) >= 70, f"expected >=70 snippets, got {len(snippets)}"
    # at least one suffix-style id (e.g. "1i" or "17i") should appear
    assert any(not s.snippet_id.isdigit() for s in snippets), (
        "expected at least one alphanumeric (suffix) snippet id"
    )
