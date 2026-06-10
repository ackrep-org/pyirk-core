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
        # Phase 2.1: ternary fact-model with full-URI predicate constants
        assert p.R83.uri in i64.rls_snippet, (
            f"I64 snippet should reference {p.R83.uri}, got: {i64.rls_snippet!r}"
        )
        assert p.R3.uri in i64.rls_snippet, (
            f"I64 snippet should reference {p.R3.uri}, got: {i64.rls_snippet!r}"
        )

    def test_i65_uses_ternary_fact_form(self, classifications):
        """Phase 2.1: I65 body must be ternary ``fact(?s, "<uri>", ?o)``,
        no auxiliary IDB predicates (R83(...) etc.) and no triples() in the body."""
        i65 = next(c for c in classifications if c.rule_short_key == "I65")
        assert "fact(" in i65.rls_snippet, "Expected fact(...) ternary pattern in I65"
        body = i65.rls_snippet.split(":-")[1]
        assert "triples(" not in body, (
            "I65 body must read from fact/3, not raw triples/3"
        )
        # The R83 URI appears as a quoted string constant, not as a predicate name
        assert f'"{p.R83.uri}"' in i65.rls_snippet, (
            f"R83 URI {p.R83.uri!r} should appear quoted in I65 snippet"
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
        """R1001 is the transitive relation defined in the spike test KB.

        Phase 2.1: facts carry the full URI as a quoted string."""
        result = generate_transitivity_facts(test_kb)
        r1001_uri = p.ds.get_entity_by_uri("irk:/h5_spike/test_kb#R1001").uri
        assert f'is_transitive("{r1001_uri}")' in result, (
            "R1001 (spike_transitive_rel) must appear in transitivity facts"
        )

    def test_contains_r17(self, test_kb):
        """R17 (is_subproperty_of) is R60-transitive in pyirk builtins."""
        result = generate_transitivity_facts(test_kb)
        assert f'is_transitive("{p.R17.uri}")' in result, (
            "R17 (is subproperty of) must appear; it has R60__is_transitive=True"
        )

    def test_no_non_transitive_relations(self, test_kb):
        """Facts should only mention relations that actually have R60=True."""
        result = generate_transitivity_facts(test_kb)
        # R3 (is_subclass_of) is NOT transitive in pyirk
        assert f'is_transitive("{p.R3.uri}")' not in result

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

    def test_contains_import_triples_with_string_format(self, test_kb):
        """Phase 2.1: every @import MUST declare format=(string,...)."""
        result = generate_rls(test_kb)
        assert '@import triples' in result
        assert 'format=(string,string,string)' in result, (
            "triples import must use format=(string,...) — otherwise CSV cells "
            "won't unify with string constants in rule heads"
        )

    def test_seeds_ternary_fact_from_triples(self, test_kb):
        """Phase 2.1: fact IDB is seeded from triples EDB."""
        result = generate_rls(test_kb)
        assert "fact(?s, ?p, ?o) :- triples(?s, ?p, ?o)" in result

    def test_contains_r83_rule_in_fact_form(self, test_kb):
        """Phase 2.1: R83-rule appears in ternary fact form with URI constants."""
        result = generate_rls(test_kb)
        assert "fact(" in result
        # R3 and R83 must appear as quoted URI strings somewhere in the body
        assert f'"{p.R3.uri}"' in result
        assert f'"{p.R83.uri}"' in result

    def test_contains_trans_rule(self, test_kb):
        """Phase 2.1: transitive closure uses ternary fact-recursion."""
        result = generate_rls(test_kb)
        assert "is_transitive(" in result
        # ternary recursion: fact(?s, ?p, ?o) :- is_transitive(?p), fact(?s, ?p, ?x), fact(?x, ?p, ?o)
        assert "is_transitive(?p)" in result and "fact(?s, ?p, ?x)" in result

    def test_contains_is_transitive_r1001(self, test_kb):
        """R1001 transitive fact must appear with full URI."""
        result = generate_rls(test_kb)
        r1001_uri = p.ds.get_entity_by_uri("irk:/h5_spike/test_kb#R1001").uri
        assert f'is_transitive("{r1001_uri}")' in result

    def test_no_transitivity_when_disabled(self, test_kb):
        result = generate_rls(test_kb, include_transitivity=False)
        assert "is_transitive(" not in result

    def test_has_export_fact(self, test_kb):
        """Phase 2.1: exactly one @export — the ternary fact relation."""
        result = generate_rls(test_kb)
        assert '@export fact :- csv{resource="output_fact.csv"} .' in result
        # No per-relation output files
        assert "@export R83" not in result
        assert "@export trans" not in result

    def test_variable_and_uri_naming(self, test_kb):
        """Generated rules use ?i1/?i2 variables and full-URI predicate constants."""
        result = generate_rls(test_kb)
        # Variable names i1 and i2 should appear (R83 chain rule pattern)
        assert "?i1" in result
        assert "?i2" in result


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
