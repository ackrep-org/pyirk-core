"""
Unit tests for pyirk.nemobridge.delegation (Phase-2 P2).

Coverage:
  * load_uri_index helper (exporter.py): reads the sidecar CSV written by
    export_datastore and produces a {short_key: uri} dict.
  * _apply_via_nemo step 5: CSV→Statement mapping with V2 (URI-based
    resolution), V3 (omit_if_existing idempotency mirror) and V5 (mod_context
    propagation). Tested against the spike test KB by triggering I66 over
    R1001 (a transitive relation defined in the test KB) and asserting that
    (a) the expected transitive-closure statements appear and (b) a second
    delegation pass produces zero new statements.

Nemo binary is required for the delegation tests; they are skipped otherwise.
"""

import csv
import os
import sys
import tempfile
import unittest

import pytest

import pyirk as p
from pyirk import core
from pyirk.nemobridge import export_datastore, load_uri_index

# Spike test-KB helper
_SPIKE_DIR = os.path.join(os.path.dirname(__file__), "..", "experiments", "h5_spike")
sys.path.insert(0, _SPIKE_DIR)
from create_test_kb import setup_test_module, TEST_MOD_URI  # noqa: E402

NEMO_BIN = os.environ.get("PYIRK_NEMO_BIN", "/home/user/bin/nmo")


class TestLoadUriIndex(unittest.TestCase):
    """load_uri_index reads the sidecar CSV produced by export_datastore."""

    def setUp(self):
        self.entities = setup_test_module()

    def tearDown(self):
        p.unload_mod(TEST_MOD_URI, strict=False)

    def test_roundtrip_with_export(self):
        """uri_index.csv written by export_datastore is read back identically."""
        with tempfile.TemporaryDirectory() as tmp:
            export_datastore(p.ds, tmp)

            mapping = load_uri_index(tmp)

            # Verify against raw CSV content
            with open(os.path.join(tmp, "uri_index.csv"), newline="") as fh:
                raw_rows = [tuple(r) for r in csv.reader(fh) if len(r) >= 2]
            raw_map = dict(raw_rows)

        self.assertEqual(mapping, raw_map,
                         "load_uri_index must reproduce the file contents 1:1")
        # Sanity: R3 is in the index and matches p.R3.uri
        self.assertEqual(mapping["R3"], p.R3.uri)

    def test_missing_file_raises(self):
        """Absent uri_index.csv → FileNotFoundError (caller's silent fallback handles it)."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_uri_index(tmp)

    def test_tolerates_optional_header_row(self):
        """A future-format header row (``short_key,uri``) is recognised and skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "uri_index.csv")
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["short_key", "uri"])  # header
                w.writerow(["R3", "irk:/builtins#R3"])
                w.writerow(["I1001", "irk:/foo#I1001"])
            mapping = load_uri_index(tmp)
        self.assertEqual(mapping, {"R3": "irk:/builtins#R3", "I1001": "irk:/foo#I1001"})


@pytest.mark.skipif(
    not os.path.exists(NEMO_BIN),
    reason=f"nmo binary not available at {NEMO_BIN} — delegation requires Nemo",
)
class TestApplyViaNemoTransitive(unittest.TestCase):
    """End-to-end test of delegation._apply_via_nemo for the I66 (transitive) rule.

    R1001 is a custom transitive relation in the spike test KB with the base
    chain I1006 → I1007 → I1008 → I1009. After applying I66 via Nemo we expect
    the transitive closure:

      I1006 → I1008
      I1006 → I1009
      I1007 → I1009

    Re-invocation of _apply_via_nemo on the resulting DataStore must add zero
    new statements (V3 idempotency).
    """

    def setUp(self):
        self.entities = setup_test_module()

    def tearDown(self):
        p.unload_mod(TEST_MOD_URI, strict=False)

    def _r1001_pairs(self):
        """Return set of (subj_key, obj_key) tuples for current R1001 statements."""
        rel_uri = self.entities["R1001"].uri
        out = set()
        for subj_uri, rel_dict in p.ds.statements.items():
            stm_or_list = rel_dict.get(rel_uri)
            if stm_or_list is None:
                continue
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s, o = stm.subject, stm.object
                if hasattr(s, "short_key") and hasattr(o, "short_key"):
                    out.add((s.short_key, o.short_key))
        return out

    def test_materialises_transitive_closure_then_idempotent(self):
        """V2-Materialisation + V3-Idempotenz: nach erstem Aufruf existieren die
        drei R1001-Closure-Statements; zweiter Aufruf liefert n_new=0 für die
        delegable-Subset (I66-Closure und parallel laufende direct rules
        i. d. R. ebenfalls bereits gesättigt).

        Hinweis: _apply_via_nemo führt nemobridge.translator.generate_rls(ds) aus
        und Nemo bewertet ALLE delegable rules gemeinsam — ergibt zusätzliche
        R83-Statements aus I64/I65. Der Test prüft explizit (a) die R1001-
        Closure-Subset und (b) V3 über die globale Idempotenz beim zweiten Lauf.
        """
        from pyirk.nemobridge.delegation import _apply_via_nemo

        baseline = self._r1001_pairs()
        # Base chain has 3 statements, no derived ones yet.
        self.assertEqual(baseline,
                         {("I1006", "I1007"), ("I1007", "I1008"), ("I1008", "I1009")},
                         f"unexpected baseline R1001: {baseline}")

        # First pass — should materialise the transitive closure (plus R83 etc.)
        n_new_first = _apply_via_nemo([p.I66], TEST_MOD_URI)
        after_first = self._r1001_pairs()

        expected_r1001_derived = {
            ("I1006", "I1008"),
            ("I1006", "I1009"),
            ("I1007", "I1009"),
        }
        new_r1001_pairs = after_first - baseline
        self.assertEqual(new_r1001_pairs, expected_r1001_derived,
                         f"V2 expected the 3 transitive-closure R1001 pairs, got {new_r1001_pairs}")
        # Return value covers the full delegable subset (R1001 closure + R83 etc.)
        self.assertGreaterEqual(n_new_first, len(expected_r1001_derived),
                                f"n_new should cover at least the R1001 closure; got {n_new_first}")

        # Second pass — V3 idempotency over the entire delegable subset
        n_new_second = _apply_via_nemo([p.I66], TEST_MOD_URI)
        after_second = self._r1001_pairs()
        self.assertEqual(n_new_second, 0,
                         f"second pass must add 0 new statements (V3), got {n_new_second}")
        self.assertEqual(after_second, after_first,
                         "second pass must not change the R1001 pair set")

    def test_out_stms_collector(self):
        """The optional out_stms collector receives one entry per materialised statement."""
        from pyirk.nemobridge.delegation import _apply_via_nemo

        collected = []
        n_new = _apply_via_nemo([p.I66], TEST_MOD_URI, out_stms=collected)
        self.assertEqual(len(collected), n_new,
                         "collector length must equal returned n_new")
        # Every collected entry must be a Statement with a known short_key predicate
        # (Nemo's delegable subset includes R1001 closure and R83 direct rules.)
        seen_pred_uris = {stm.predicate.uri for stm in collected}
        self.assertTrue(seen_pred_uris,
                        "collector should contain at least one statement")
        # R1001 closure must be in there
        self.assertIn(self.entities["R1001"].uri, seen_pred_uris)


if __name__ == "__main__":
    unittest.main()
