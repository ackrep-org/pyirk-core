"""
Phase-2 P4 — extra unit tests for the nemo-delegation pipeline.

Coverage:
  * Idempotency end-to-end on a mini-KB: two consecutive
    ``apply_semantic_rules(*all_rules, exhaust=True)`` calls — the first one
    materialises at least one R3-driven R83 derivation, the second one adds
    exactly 0 new statements (V3 ``omit_if_existing`` mirror, exercised
    through the full V4 fixpoint loop).
  * CSV → Statement mapping with the real Nemo binary: drives
    ``_apply_via_nemo`` against the spike test-KB and asserts that
      - ``n_new == len(out_stms)`` (the collector matches the return value),
      - every materialised statement has a URI-resolved Item subject, an
        Item object and a Relation predicate (V2 — strict URI resolution),
      - every materialised statement carries the requested mod_context_uri
        (V5 — mirrored from the native pathway).
  * Plateau check (optional / belt-and-braces): after a first
    ``apply_semantic_rules`` pass the statement count is stable, i.e. a
    second pass returns the same number of statements as before.

All Nemo-binary tests skip cleanly when ``/home/user/bin/nmo`` (or
PYIRK_NEMO_BIN) is absent, with a precise reason.
"""

import os
import sys
import unittest

import pytest

import pyirk as p
from pyirk import core, ruleengine

# Reuse the spike-KB helper to avoid duplicating the fixture data.
_SPIKE_DIR = os.path.join(os.path.dirname(__file__), "..", "experiments", "h5_spike")
sys.path.insert(0, _SPIKE_DIR)
from create_test_kb import setup_test_module, TEST_MOD_URI  # noqa: E402

NEMO_BIN = os.environ.get("PYIRK_NEMO_BIN", "/home/user/bin/nmo")
_NO_NEMO_REASON = (
    f"nmo binary not available at {NEMO_BIN} — the delegation pathway needs Nemo "
    "to materialise CSV outputs into Statements (V2+V3+V5)."
)


def _count_statements(ds) -> int:
    """Total number of subject-role Statement objects in ds.statements."""
    n = 0
    for _subj_uri, rel_dict in ds.statements.items():
        for _rel_uri, stm_or_list in rel_dict.items():
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            n += len(stms)
    return n


def _r83_pairs(ds):
    """Return the current set of (subj_key, obj_key) tuples for R83 statements."""
    out = set()
    r83_uri = p.R83.uri
    for _subj_uri, rel_dict in ds.statements.items():
        stm_or_list = rel_dict.get(r83_uri)
        if stm_or_list is None:
            continue
        stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
        for stm in stms:
            s, o = stm.subject, stm.object
            if hasattr(s, "short_key") and hasattr(o, "short_key"):
                out.add((s.short_key, o.short_key))
    return out


@pytest.mark.skipif(not os.path.exists(NEMO_BIN), reason=_NO_NEMO_REASON)
class TestApplySemanticRulesIdempotent(unittest.TestCase):
    """End-to-end idempotency through ``apply_semantic_rules`` with the V4 loop.

    The spike test-KB has a complete R3 subclass chain (I1001..I1005) which
    triggers at least the R3 → R83 direct rule (I64). Running
    ``apply_semantic_rules(exhaust=True)`` once with the delegation flag
    set must populate the R83 closure; a second call on the *same*
    DataStore must add exactly 0 new statements.
    """

    def setUp(self):
        self.entities = setup_test_module()
        # Always enable the delegation flag for this class; reset in tearDown.
        self._prev_flag = os.environ.get("PYIRK_NEMO_DELEGATION")
        os.environ["PYIRK_NEMO_DELEGATION"] = "1"

    def tearDown(self):
        if self._prev_flag is None:
            os.environ.pop("PYIRK_NEMO_DELEGATION", None)
        else:
            os.environ["PYIRK_NEMO_DELEGATION"] = self._prev_flag
        p.unload_mod(TEST_MOD_URI, strict=False)

    def test_second_pass_yields_zero_new_statements(self):
        """Two consecutive apply_semantic_rules — second pass adds 0 stmts."""
        all_rules = ruleengine.get_all_rules()

        before_r83 = _r83_pairs(core.ds)
        before_total = _count_statements(core.ds)

        res1 = ruleengine.apply_semantic_rules(
            *all_rules, mod_context_uri=TEST_MOD_URI, exhaust=True,
        )
        after_r83 = _r83_pairs(core.ds)
        after_total = _count_statements(core.ds)

        # First pass must derive at least one fresh R83 statement
        # (R3-chain → R83-closure). If not, the spike-KB layout has drifted
        # in a way that invalidates this test fixture — fail loudly.
        self.assertGreater(
            len(after_r83 - before_r83), 0,
            "expected at least one new R83 statement from the R3 chain — "
            "fixture drift?",
        )
        self.assertGreater(
            len(res1.new_statements), 0,
            "first pass should report new_statements; got an empty result.",
        )
        self.assertGreater(after_total, before_total,
                           "total statement count must grow after the first pass.")

        # Second pass — V3 + V4 idempotency end-to-end
        snapshot_r83 = set(after_r83)
        snapshot_total = after_total

        res2 = ruleengine.apply_semantic_rules(
            *all_rules, mod_context_uri=TEST_MOD_URI, exhaust=True,
        )
        self.assertEqual(
            len(res2.new_statements), 0,
            f"second pass must report 0 new statements (V3+V4 idempotency); "
            f"got {len(res2.new_statements)}",
        )
        self.assertEqual(_r83_pairs(core.ds), snapshot_r83,
                         "second pass must not change the R83 pair set.")
        self.assertEqual(_count_statements(core.ds), snapshot_total,
                         "second pass must not grow the total statement count.")


@pytest.mark.skipif(not os.path.exists(NEMO_BIN), reason=_NO_NEMO_REASON)
class TestApplyViaNemoMapping(unittest.TestCase):
    """CSV → Statement mapping with the live Nemo binary."""

    def setUp(self):
        self.entities = setup_test_module()

    def tearDown(self):
        p.unload_mod(TEST_MOD_URI, strict=False)

    def test_out_stms_matches_n_new_and_uri_resolution(self):
        """n_new == len(out_stms), every stmt URI-resolved, mod_context honoured."""
        from pyirk.nemobridge.delegation import _apply_via_nemo

        collected: list = []
        n_new = _apply_via_nemo([p.I64, p.I66], TEST_MOD_URI, out_stms=collected)

        # Collector contract — one entry per inserted statement.
        self.assertEqual(
            n_new, len(collected),
            f"collector length must equal returned n_new "
            f"({n_new} vs {len(collected)})",
        )
        self.assertGreater(
            n_new, 0,
            "expected at least one materialised statement from the spike-KB.",
        )

        # V2 — every endpoint and the predicate must be a fully-resolved entity
        # (i.e. has a non-empty .uri). The repr-based fallback for literals must
        # NOT trigger here because the spike-KB's R3/R1001 closure is entity-only.
        for stm in collected:
            self.assertIsInstance(stm, core.Statement)
            self.assertTrue(hasattr(stm.subject, "uri"))
            self.assertTrue(hasattr(stm.object, "uri"))
            self.assertTrue(hasattr(stm.predicate, "uri"))
            self.assertIsInstance(stm.subject, core.Item)
            self.assertIsInstance(stm.predicate, core.Relation)
            self.assertIsInstance(stm.object, core.Item)

        # V5 — mod_context_uri propagation. ``uri_context`` sets the active
        # module URI; the Statement constructor copies that into
        # ``base_uri`` (and registers the statement under
        # ``ds.stms_created_in_mod[mod_uri]``). Both views should reflect
        # TEST_MOD_URI.
        expected = TEST_MOD_URI
        observed = {getattr(stm, "base_uri", None) for stm in collected}
        self.assertEqual(
            observed, {expected},
            f"V5: every new statement should carry base_uri={expected!r}; "
            f"got distinct values {observed!r}",
        )
        registered = core.ds.stms_created_in_mod.get(expected, {})
        for stm in collected:
            self.assertIn(
                stm.uri, registered,
                f"V5: statement {stm.uri} must be registered under "
                f"ds.stms_created_in_mod[{expected!r}].",
            )

    def test_second_call_is_idempotent_with_empty_collector(self):
        """V3 mirror: second _apply_via_nemo call → n_new == 0, collector untouched."""
        from pyirk.nemobridge.delegation import _apply_via_nemo

        # First pass populates the closure.
        first_collected: list = []
        n_first = _apply_via_nemo([p.I64, p.I66], TEST_MOD_URI,
                                  out_stms=first_collected)
        self.assertGreater(n_first, 0)
        self.assertEqual(len(first_collected), n_first)

        # Second pass — must be a no-op for the delegable subset.
        second_collected: list = []
        n_second = _apply_via_nemo([p.I64, p.I66], TEST_MOD_URI,
                                   out_stms=second_collected)
        self.assertEqual(
            n_second, 0,
            f"V3 idempotency: second pass must add 0 statements; got {n_second}",
        )
        self.assertEqual(
            second_collected, [],
            "out_stms collector must remain empty on an idempotent pass.",
        )


if __name__ == "__main__":
    unittest.main()
