"""
Unit tests for pyirk.nemobridge.translator.

Tests verify the rule classifier and .rls code generator without requiring
the Nemo binary.  The test KB is the h5_spike test knowledge base.
"""

import json
import os
import sys
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SPIKE_DIR = os.path.join(REPO_ROOT, "experiments", "h5_spike")
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
sys.path.insert(0, SPIKE_DIR)

import pyirk as p
from create_test_kb import setup_test_module, TEST_MOD_URI
from pyirk.nemobridge import (
    classify_rules,
    generate_transitivity_facts,
    generate_rls,
    classification_to_json,
    RuleClassification,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_kb():
    """Build the h5_spike test KB once per module, then tear it down."""
    setup_test_module()
    yield p.ds
    p.unload_mod(TEST_MOD_URI, strict=False)


@pytest.fixture(scope="module")
def classifications(test_kb):
    return classify_rules(test_kb)


# ─────────────────────────────────────────────────────────────────────────────
# classify_rules tests
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyRules:
    def test_returns_nonempty_list(self, classifications):
        assert len(classifications) > 0

    def test_all_have_valid_category(self, classifications):
        valid = {"direct", "transitive", "python_only"}
        for c in classifications:
            assert c.category in valid, f"{c.rule_short_key} has invalid category: {c.category!r}"

    def test_all_have_nonempty_reason(self, classifications):
        for c in classifications:
            assert c.reason, f"{c.rule_short_key} has empty reason"

    def test_all_have_short_key_and_label(self, classifications):
        for c in classifications:
            assert c.rule_short_key, f"Missing short_key in {c}"
            assert c.label, f"Missing label in {c}"

    def test_i64_is_direct(self, classifications):
        i64 = next((c for c in classifications if c.rule_short_key == "I64"), None)
        assert i64 is not None, "I64 not found in classifications"
        assert i64.category == "direct"
        assert i64.rls_snippet is not None

    def test_i65_is_direct(self, classifications):
        i65 = next((c for c in classifications if c.rule_short_key == "I65"), None)
        assert i65 is not None, "I65 not found in classifications"
        assert i65.category == "direct"
        assert i65.rls_snippet is not None

    def test_i66_is_transitive(self, classifications):
        i66 = next((c for c in classifications if c.rule_short_key == "I66"), None)
        assert i66 is not None, "I66 not found in classifications"
        assert i66.category == "transitive"
        assert i66.rls_snippet is None  # no snippet for transitive rules

    def test_direct_rules_have_snippet(self, classifications):
        for c in classifications:
            if c.category == "direct":
                assert c.rls_snippet, f"Direct rule {c.rule_short_key} missing rls_snippet"

    def test_nondirect_rules_have_no_snippet(self, classifications):
        for c in classifications:
            if c.category != "direct":
                assert c.rls_snippet is None, (
                    f"Non-direct rule {c.rule_short_key} (category={c.category}) "
                    "unexpectedly has a rls_snippet"
                )

    def test_i64_snippet_contains_r3_and_r83(self, classifications):
        i64 = next(c for c in classifications if c.rule_short_key == "I64")
        assert "R83" in i64.rls_snippet
        assert "R3" in i64.rls_snippet

    def test_i65_snippet_uses_derived_r83_not_triples(self, classifications):
        """I65's premise uses R83 (a derived predicate), so the body must use R83(...)
        directly, NOT triples(..., R83, ...)."""
        i65 = next(c for c in classifications if c.rule_short_key == "I65")
        assert "R83(" in i65.rls_snippet, "Expected R83(...) pattern in I65 body"
        assert "triples(" not in i65.rls_snippet.split(":-")[1], (
            "I65 body should use R83(...) directly, not triples(..., R83, ...)"
        )

    def test_all_types_are_dataclass_instances(self, classifications):
        for c in classifications:
            assert isinstance(c, RuleClassification)


# ─────────────────────────────────────────────────────────────────────────────
# generate_transitivity_facts tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateTransitivityFacts:
    def test_returns_string(self, test_kb):
        result = generate_transitivity_facts(test_kb)
        assert isinstance(result, str)

    def test_contains_r1001(self, test_kb):
        """R1001 is the transitive relation defined in the spike test KB."""
        result = generate_transitivity_facts(test_kb)
        assert "is_transitive(R1001)" in result, (
            "R1001 (spike_transitive_rel) must appear in transitivity facts"
        )

    def test_contains_r17(self, test_kb):
        """R17 (is_subproperty_of) is R60-transitive in pyirk builtins."""
        result = generate_transitivity_facts(test_kb)
        assert "is_transitive(R17)" in result, (
            "R17 (is subproperty of) must appear; it has R60__is_transitive=True"
        )

    def test_no_non_transitive_relations(self, test_kb):
        """Facts should only mention relations that actually have R60=True."""
        result = generate_transitivity_facts(test_kb)
        # R3 (is_subclass_of) is NOT transitive in pyirk
        assert "is_transitive(R3)" not in result

    def test_each_fact_ends_with_period(self, test_kb):
        result = generate_transitivity_facts(test_kb)
        for line in result.splitlines():
            line = line.strip()
            if line.startswith("is_transitive("):
                assert line.endswith("."), f"Fact line missing trailing period: {line!r}"


# ─────────────────────────────────────────────────────────────────────────────
# generate_rls tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateRls:
    def test_returns_string(self, test_kb):
        result = generate_rls(test_kb)
        assert isinstance(result, str)

    def test_contains_import_triples(self, test_kb):
        result = generate_rls(test_kb)
        assert '@import triples' in result

    def test_contains_r83_rule(self, test_kb):
        """R83(?i2, ?i1) :- triples(?i2, R3, ?i1) — from spike rules_r1.rls."""
        result = generate_rls(test_kb)
        assert "R83(" in result
        assert "triples(" in result

    def test_contains_trans_rule(self, test_kb):
        """Transitive closure rule should be present."""
        result = generate_rls(test_kb)
        assert "trans(" in result
        assert "is_transitive(" in result

    def test_contains_is_transitive_r1001(self, test_kb):
        """The R1001 is_transitive fact must appear in the combined RLS."""
        result = generate_rls(test_kb)
        assert "is_transitive(R1001)" in result

    def test_no_transitivity_when_disabled(self, test_kb):
        result = generate_rls(test_kb, include_transitivity=False)
        assert "is_transitive(" not in result
        assert "trans(" not in result

    def test_has_export_r83(self, test_kb):
        result = generate_rls(test_kb)
        assert "@export R83" in result

    def test_has_export_trans(self, test_kb):
        result = generate_rls(test_kb)
        assert "@export trans" in result

    def test_loosely_matches_spike_r1_rls(self, test_kb):
        """The generated RLS should loosely match spike rules_r1.rls patterns.
        Spike rule: is_generalized_subclass(?i2, ?i1) :- is_subclass_of(?i2, ?i1)
        Our rule:   R83(?i2, ?i1) :- triples(?i2, R3, ?i1)
        Both express the same R3→R83 mapping, just with different predicate names.
        """
        result = generate_rls(test_kb)
        # Variable names i1 and i2 should appear
        assert "?i1" in result
        assert "?i2" in result
        # R83 and R3 should appear
        assert "R83" in result
        assert "R3" in result

    def test_loosely_matches_spike_r2_rls(self, test_kb):
        """Transitivity rule pattern should match the spike rules_r2.rls structure."""
        result = generate_rls(test_kb)
        # Recursive trans rule should be present
        assert "trans(?i1" in result or ("trans(" in result and "is_transitive" in result)


# ─────────────────────────────────────────────────────────────────────────────
# classification_to_json tests
# ─────────────────────────────────────────────────────────────────────────────

class TestClassificationToJson:
    def test_returns_valid_json(self, classifications):
        result = classification_to_json(classifications)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_json_has_expected_fields(self, classifications):
        result = classification_to_json(classifications)
        parsed = json.loads(result)
        for item in parsed:
            assert "rule_short_key" in item
            assert "category" in item
            assert "reason" in item
            assert "rls_snippet" in item
            assert "rule_uri" in item
            assert "label" in item

    def test_json_count_matches_input(self, classifications):
        result = classification_to_json(classifications)
        parsed = json.loads(result)
        assert len(parsed) == len(classifications)

    def test_empty_list_valid(self):
        result = classification_to_json([])
        assert json.loads(result) == []
