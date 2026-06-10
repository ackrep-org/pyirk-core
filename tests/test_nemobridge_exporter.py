"""
Unit tests for pyirk.nemobridge.exporter.

Tests run without Nemo binary — only the export/filter logic is covered here.
"""

import csv
import os
import sys
import tempfile
import unittest

import pyirk as p
from pyirk.nemobridge import export_datastore, export_relation_facts, is_scope_internal

# Spike test-KB helper (needed for smoke test)
_SPIKE_DIR = os.path.join(os.path.dirname(__file__), "..", "experiments", "h5_spike")
sys.path.insert(0, _SPIKE_DIR)
from create_test_kb import setup_test_module, TEST_MOD_URI  # noqa: E402

BASELINE_R1_COUNT = 49  # from experiments/h5_spike/baseline_r1.json


class TestSmokeExport(unittest.TestCase):
    """Smoke test: exporter runs against the spike test-KB without error."""

    def setUp(self):
        # setup_test_module() handles register_mod + start_mod + end_mod internally
        self.entities = setup_test_module()

    def tearDown(self):
        p.unload_mod(TEST_MOD_URI, strict=False)

    def test_export_relation_facts_r3(self):
        """export_relation_facts with R3 should yield BASELINE_R1_COUNT rows."""
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "r3.csv")
            count = export_relation_facts(p.ds, p.R3.uri, csv_path, arity=2)
            self.assertEqual(
                count,
                BASELINE_R1_COUNT,
                f"Expected {BASELINE_R1_COUNT} R3 facts, got {count}",
            )
            # Verify CSV actually has that many rows
            with open(csv_path) as fh:
                rows = [r for r in csv.reader(fh)]
            self.assertEqual(len(rows), BASELINE_R1_COUNT)
            # Each row must be 2-column (subject_key, object_key)
            for row in rows:
                self.assertEqual(len(row), 2, f"Expected 2 columns, got: {row}")

    def test_export_relation_facts_arity3(self):
        """arity=3 export includes the predicate column as a full URI."""
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "r3_3col.csv")
            count = export_relation_facts(p.ds, p.R3.uri, csv_path, arity=3)
            self.assertEqual(count, BASELINE_R1_COUNT)
            with open(csv_path) as fh:
                rows = list(csv.reader(fh))
            for row in rows:
                self.assertEqual(len(row), 3, f"Expected 3 columns, got: {row}")
                self.assertEqual(
                    row[1], p.R3.uri,
                    f"Column 1 should be the full R3 URI, got: {row}",
                )

    def test_export_datastore_smoke(self):
        """export_datastore returns a dict with expected keys and non-empty triples."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_datastore(p.ds, tmp)
        self.assertIn("predicate_counts", result)
        self.assertIn("qualifier_counts", result)
        self.assertIn("total_triples", result)
        self.assertIn("total_qualified", result)
        self.assertIn("paths", result)
        # There must be some triples in the DS
        self.assertGreater(result["total_triples"], 0)
        # R3 must be one of the predicates
        self.assertIn("R3", result["predicate_counts"])
        self.assertEqual(result["predicate_counts"]["R3"], BASELINE_R1_COUNT)

    def test_export_datastore_per_predicate(self):
        """per_predicate=True produces triples__R3.csv with 2-column rows."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_datastore(p.ds, tmp, per_predicate=True)
            r3_path = result["paths"]["per_predicate"].get("R3")
            self.assertIsNotNone(r3_path, "triples__R3.csv should be created")
            with open(r3_path) as fh:
                rows = list(csv.reader(fh))
            self.assertEqual(len(rows), BASELINE_R1_COUNT)
            for row in rows:
                self.assertEqual(len(row), 2)

    def test_audit_return_counts_are_consistent(self):
        """predicate_counts total should equal total_triples + total_qualified."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_datastore(p.ds, tmp)
        total_from_preds = sum(result["predicate_counts"].values())
        expected = result["total_triples"] + result["total_qualified"]
        self.assertEqual(total_from_preds, expected)

    def test_export_datastore_uri_index(self):
        """uri_index.csv carries full URIs for every short_key in the export (V2).

        Verifies:
          - uri_index.csv exists in out_dir and is reachable via paths["uri_index"].
          - No duplicate short_keys.
          - URI for at least one known short_key matches the live entity.uri,
            so the index can drive module-context-aware reverse resolution.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = export_datastore(p.ds, tmp)
            self.assertIn("uri_index", result["paths"])
            idx_path = result["paths"]["uri_index"]
            self.assertTrue(
                os.path.exists(idx_path),
                f"uri_index.csv should exist at {idx_path}",
            )
            with open(idx_path) as fh:
                rows = list(csv.reader(fh))

        self.assertGreater(len(rows), 0, "uri_index.csv should not be empty")
        # Each row is (short_key, uri)
        for row in rows:
            self.assertEqual(len(row), 2, f"Expected 2 columns, got: {row}")

        short_keys = [r[0] for r in rows]
        self.assertEqual(
            len(short_keys),
            len(set(short_keys)),
            "uri_index.csv must not contain duplicate short_keys",
        )
        # Sorted ascending
        self.assertEqual(short_keys, sorted(short_keys),
                         "uri_index.csv rows must be sorted by short_key")

        index_map = dict(rows)

        # R3 is a builtin relation that must appear in the export (used by the
        # test-KB triples). Its index URI must match the live entity.uri.
        self.assertIn("R3", index_map, "R3 should be in uri_index.csv")
        self.assertEqual(
            index_map["R3"],
            p.R3.uri,
            f"R3 uri mismatch: index={index_map['R3']!r}, live={p.R3.uri!r}",
        )

        # At least one test-KB item should appear and resolve to a uri under
        # the test module — proves that index distinguishes builtin from
        # non-builtin entities (module-context preserved).
        test_item_keys = [k for k in self.entities if k.startswith("I")]
        matched = 0
        for k in test_item_keys:
            if k in index_map:
                self.assertEqual(
                    index_map[k],
                    self.entities[k].uri,
                    f"{k} uri mismatch: index={index_map[k]!r}, "
                    f"live={self.entities[k].uri!r}",
                )
                matched += 1
        self.assertGreater(
            matched, 0,
            "Expected at least one test-KB item in uri_index.csv",
        )


class TestScopeFilter(unittest.TestCase):
    """Test is_scope_internal filter on entities from the live DataStore."""

    def setUp(self):
        self.entities = setup_test_module()

    def tearDown(self):
        p.unload_mod(TEST_MOD_URI, strict=False)

    def test_normal_items_not_scope_internal(self):
        """Test-KB items I1001-I1009 must NOT be scope-internal."""
        for key in ("I1001", "I1002", "I1003", "I1004", "I1005",
                    "I1006", "I1007", "I1008", "I1009"):
            entity = self.entities[key]
            self.assertFalse(
                is_scope_internal(entity),
                f"{key} should not be scope-internal",
            )

    def test_scope_internal_items_are_detected(self):
        """Items inside a rule scope (cm.i1, cm.i2, ...) are flagged as scope-internal.

        pyirk rule I64 defines scope-internal prototype items via cm.new_var().
        These items have a direct R20__has_defining_scope relation pointing to the
        rule's setting-scope item.  They are retrievable via
        rule.scp__setting.get_inv_relations("R20__has_defining_scope", return_subj=True).
        """
        # Get scope-internal items from I64's setting scope (defined in builtin_entities)
        scope_vars = p.I64.scp__setting.get_inv_relations(
            "R20__has_defining_scope", return_subj=True
        )
        if not scope_vars:
            self.skipTest(
                "I64.scp__setting has no scope-internal items — "
                "builtin_entities definition may have changed."
            )

        for entity in scope_vars:
            self.assertTrue(
                is_scope_internal(entity),
                f"{entity.short_key} is a scope-var of I64 but is_scope_internal returned False",
            )

    def test_invalid_arity_raises(self):
        """export_relation_facts with invalid arity must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                export_relation_facts(p.ds, p.R3.uri, os.path.join(tmp, "x.csv"), arity=4)


if __name__ == "__main__":
    unittest.main()
