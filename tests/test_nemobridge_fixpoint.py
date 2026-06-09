"""
Unit tests for the V4 bounded nemo↔python fixpoint loop in
``ruleengine.apply_semantic_rules`` (Phase-2 P3).

Coverage:
  * Convergence path: after one round of mutual triggering both blocks report
    0 new statements; the loop exits cleanly with ``iters >= 2`` and no
    ``RuntimeError``.
  * ``exhaust=False`` semantics: exactly one V4 iteration runs — ``_apply_via_nemo``
    is called exactly once.
  * CAP enforcement: a divergent stub (every iteration yields > 0 new
    statements from both blocks) triggers ``RuntimeError`` after
    ``_NEMO_FIXPOINT_CAP + 1`` iterations.

The tests stub ``_apply_via_nemo``, ``_nemo_available`` and
``_split_rules_by_nemo_delegation`` so the loop mechanics can be tested
deterministically without depending on the Nemo binary or a real KB. The
convergence test additionally has a Nemo-binary-backed variant in
``tests/test_nemobridge_delegation.py``; here we only verify the loop control
flow.
"""

import os
import unittest
from unittest import mock

import pyirk as p
from pyirk import core, ruleengine
from pyirk.ruleengine import ReportingMultiRuleResult, ReportingRuleResult


def _make_fake_statement(idx: int):
    """A unique stand-in for a ``core.Statement``.

    ``RuleResult.add_statement`` only stores the object in a list and indexes
    it by ``stm.predicate.uri`` for the rel_map. We provide a minimal duck-typed
    object that satisfies both — using a stable per-call-site URI keeps
    ``add_statement``'s ``assert stm not in self.new_statements`` happy across
    iterations because each idx produces a fresh sentinel.
    """
    fake_pred = mock.Mock()
    fake_pred.uri = f"irk:/test/fake#R{idx}"
    fake_stm = mock.Mock()
    fake_stm.predicate = fake_pred
    return fake_stm


def _empty_python_result():
    """Result of a python rule that produces nothing this iteration."""
    res = ReportingRuleResult(raworker=None)
    res._rule = None
    res.apply_time = 0
    return res


def _python_result_with_one_stm(stm):
    """Result of a python rule that produces exactly one new statement."""
    res = ReportingRuleResult(raworker=None)
    res._rule = None
    res.apply_time = 0
    res.add_statement(stm)
    return res


class TestV4FixpointLoop(unittest.TestCase):
    """V4 loop control flow — Nemo binary not required (everything is stubbed)."""

    def setUp(self):
        # Save existing flag so we can restore in tearDown.
        self._prev_flag = os.environ.get("PYIRK_NEMO_DELEGATION")
        os.environ["PYIRK_NEMO_DELEGATION"] = "1"

    def tearDown(self):
        if self._prev_flag is None:
            os.environ.pop("PYIRK_NEMO_DELEGATION", None)
        else:
            os.environ["PYIRK_NEMO_DELEGATION"] = self._prev_flag

    def _patch_classification(self, delegated, remaining):
        """Patch ``_nemo_available`` (→ True) and ``_split_rules_by_nemo_delegation``."""
        ctx_nemo = mock.patch(
            "pyirk.nemobridge.delegation._nemo_available", return_value=True
        )
        ctx_split = mock.patch(
            "pyirk.nemobridge.delegation._split_rules_by_nemo_delegation",
            return_value=(list(delegated), list(remaining)),
        )
        return ctx_nemo, ctx_split

    def test_loop_converges_after_two_iterations(self):
        """Iter 1: both blocks add 1 stm each. Iter 2: both return 0. Loop exits cleanly.

        Verifies the V4 fixpoint mechanic: a Python rule may produce a fact
        that re-triggers the delegable subset; a second Nemo pass picks up
        nothing new; the loop converges. ``iters >= 2`` is the load-bearing
        property — exactly the case the V4 design exists for.
        """
        delegated_rule = mock.Mock(name="delegated_rule")
        remaining_rule = mock.Mock(name="remaining_rule")

        # _apply_via_nemo: iter 1 → 1 new (append to out_stms), iter 2+ → 0.
        nemo_call_count = {"n": 0}

        def nemo_stub(delegated, mod_uri, *, out_stms=None):
            nemo_call_count["n"] += 1
            if nemo_call_count["n"] == 1:
                if out_stms is not None:
                    out_stms.append(_make_fake_statement(idx=1000 + nemo_call_count["n"]))
                return 1
            return 0

        # apply_semantic_rule: iter 1 → 1 new stm, iter 2+ → 0.
        python_call_count = {"n": 0}

        def python_stub(rule, mod_uri):
            python_call_count["n"] += 1
            if python_call_count["n"] == 1:
                return _python_result_with_one_stm(
                    _make_fake_statement(idx=2000 + python_call_count["n"])
                )
            return _empty_python_result()

        ctx_nemo, ctx_split = self._patch_classification(
            [delegated_rule], [remaining_rule]
        )
        with ctx_nemo, ctx_split, \
                mock.patch("pyirk.nemobridge.delegation._apply_via_nemo",
                           side_effect=nemo_stub) as mock_nemo, \
                mock.patch("pyirk.ruleengine.apply_semantic_rule",
                           side_effect=python_stub) as mock_py:
            res = ruleengine.apply_semantic_rules(
                delegated_rule, remaining_rule, exhaust=True,
            )

        self.assertIsInstance(res, ReportingMultiRuleResult)
        # Two Nemo calls (iter 1 produced, iter 2 confirms convergence).
        self.assertEqual(mock_nemo.call_count, 2,
                         f"expected 2 Nemo calls (iter1=produce, iter2=confirm), got {mock_nemo.call_count}")
        # Two python passes over the single remaining rule.
        self.assertEqual(mock_py.call_count, 2,
                         f"expected 2 python passes, got {mock_py.call_count}")
        # Total new statements: 1 nemo + 1 python from iter 1.
        self.assertEqual(len(res.new_statements), 2,
                         f"expected 2 new statements total, got {len(res.new_statements)}")

    def test_exhaust_false_runs_exactly_one_iteration(self):
        """``exhaust=False`` must do exactly one Nemo + one python pass, period."""
        delegated_rule = mock.Mock(name="delegated_rule")
        remaining_rule = mock.Mock(name="remaining_rule")

        # Both blocks would happily produce in every iteration — but exhaust=False
        # must terminate the loop after the very first iteration anyway.
        def nemo_stub(delegated, mod_uri, *, out_stms=None):
            if out_stms is not None:
                out_stms.append(_make_fake_statement(idx=3000 + len(out_stms)))
            return 1

        py_idx = {"n": 0}

        def python_stub(rule, mod_uri):
            py_idx["n"] += 1
            return _python_result_with_one_stm(_make_fake_statement(idx=4000 + py_idx["n"]))

        ctx_nemo, ctx_split = self._patch_classification(
            [delegated_rule], [remaining_rule]
        )
        with ctx_nemo, ctx_split, \
                mock.patch("pyirk.nemobridge.delegation._apply_via_nemo",
                           side_effect=nemo_stub) as mock_nemo, \
                mock.patch("pyirk.ruleengine.apply_semantic_rule",
                           side_effect=python_stub) as mock_py:
            ruleengine.apply_semantic_rules(
                delegated_rule, remaining_rule, exhaust=False,
            )

        # The cardinal property: exactly one Nemo call.
        self.assertEqual(mock_nemo.call_count, 1,
                         f"exhaust=False must call _apply_via_nemo exactly once, got {mock_nemo.call_count}")
        # Exactly one python pass over the single remaining rule.
        self.assertEqual(mock_py.call_count, 1,
                         f"exhaust=False must do exactly one python pass, got {mock_py.call_count}")

    def test_cap_triggers_runtime_error(self):
        """A divergent loop hits the CAP and raises ``RuntimeError``.

        Stub setup: every iteration both blocks claim 1 new statement (using
        unique sentinels so add_statement's no-duplicate assert holds). The
        loop never converges → after ``_NEMO_FIXPOINT_CAP + 1`` iterations the
        RuntimeError is raised.
        """
        delegated_rule = mock.Mock(name="delegated_rule")
        remaining_rule = mock.Mock(name="remaining_rule")

        nemo_idx = {"n": 0}

        def nemo_stub(delegated, mod_uri, *, out_stms=None):
            nemo_idx["n"] += 1
            if out_stms is not None:
                out_stms.append(_make_fake_statement(idx=5000 + nemo_idx["n"]))
            return 1

        py_idx = {"n": 0}

        def python_stub(rule, mod_uri):
            py_idx["n"] += 1
            return _python_result_with_one_stm(_make_fake_statement(idx=6000 + py_idx["n"]))

        ctx_nemo, ctx_split = self._patch_classification(
            [delegated_rule], [remaining_rule]
        )
        with ctx_nemo, ctx_split, \
                mock.patch("pyirk.nemobridge.delegation._apply_via_nemo",
                           side_effect=nemo_stub) as mock_nemo, \
                mock.patch("pyirk.ruleengine.apply_semantic_rule",
                           side_effect=python_stub):
            with self.assertRaises(RuntimeError) as cm:
                ruleengine.apply_semantic_rules(
                    delegated_rule, remaining_rule, exhaust=True,
                )

        self.assertIn("fixpoint did not converge", str(cm.exception))
        # The cap is 50; the loop raises on iters > 50, i.e. on the 51st iteration.
        self.assertEqual(mock_nemo.call_count, ruleengine._NEMO_FIXPOINT_CAP + 1,
                         f"loop must raise on iter cap+1 ({ruleengine._NEMO_FIXPOINT_CAP + 1}), "
                         f"_apply_via_nemo was called {mock_nemo.call_count}x")


if __name__ == "__main__":
    unittest.main()
