"""Tests for the ``pyirk --import-lean ...`` CLI hook (authoring substrate)."""

import json
import os
import tempfile
import types
import unittest
from os.path import join as pjoin
from pathlib import Path

import pyirk as p
from pyirk import authoring, script
from pyirk.authoring import lean as authoring_lean

from .settings import HousekeeperMixin, TEST_DATA_PATH_MA

# Lean fixtures live under this repo's tests/test_data/lean. We compute the path
# from __file__ because TEST_DATA_DIR1 in settings.py resolves to a sibling
# pyirk-core checkout, which does not carry the lean/ subdir.
_LOCAL_TEST_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")


# Canonical OK block: only references built-in entities and R9999 (declared in the
# bootstrap). Keeps the test independent of the OCSE subset's I-key churn.
CANNED_OK_BLOCK = (
    "OK:\n"
    "```python\n"
    "I7777 = p.create_item(\n"
    '    R1__has_label="trivial identity (1=1)",\n'
    '    R2__has_description="theorem: 1 equals 1",\n'
    '    R4__is_instance_of=p.I15["implication proposition"],\n'
    '    R9999__has_source_reference="Lean / mathlib4: .foo",\n'
    ")\n"
    "```\n"
)


def _build_args(**overrides) -> types.SimpleNamespace:
    """Build an argparse-like Namespace with all CLI flags this handler reads."""
    defaults = dict(
        import_lean=None,
        target=None,
        theorem=None,
        all_theorems=False,
        ocse_uri=None,
        ocse_path=None,
        working_uri=None,
        source_url=None,
        fork_policy="ask",
        stats_jsonl=None,
        keep_going=False,
        resume=False,
        limit=0,
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


class Test_LeanParser(unittest.TestCase):
    """Pure parsing tests for ``authoring.lean.parse_theorems`` (no pyirk state)."""

    # Distills the structure of mathlib's LinearAlgebra/Trace.lean that exposed
    # two parser bugs: (1) ``lemma`` declarations were not matched at all,
    # (2) a ``/--``-docstring belonging to a *non-theorem* declaration (here a
    # ``def``) backtracked across its own ``-/`` and engulfed every theorem up
    # to the next docstring'd one, silently dropping them from the parse.
    LEAN_SNIPPET = (
        "namespace LinearMap\n"
        "\n"
        "/-- The trace of an endomorphism given a basis. -/\n"
        "def traceAux : Foo :=\n"
        "  bar\n"
        "\n"
        "theorem traceAux_def (b : Basis) :\n"
        "    traceAux R b f = Matrix.trace :=\n"
        "  rfl\n"
        "\n"
        "lemma comp_add (h : Foo) (dt : R) :\n"
        "    IsBar (fun t => g (t + dt)) :=\n"
        "  baz\n"
        "\n"
        "/-- doc for the last one -/\n"
        "theorem with_doc : 1 = 1 := by simp\n"
        "\n"
        "end LinearMap\n"
    )

    def test_parses_lemma_and_does_not_engulf_after_def_docstring(self):
        theorems = authoring_lean.parse_theorems(self.LEAN_SNIPPET)
        names = [t.name for t in theorems]
        self.assertEqual(names, ["traceAux_def", "comp_add", "with_doc"])

        by_name = {t.name: t for t in theorems}
        # the def's docstring must not be attributed to the following theorem
        self.assertEqual(by_name["traceAux_def"].docstring, "")
        self.assertEqual(by_name["comp_add"].docstring, "")
        self.assertEqual(by_name["with_doc"].docstring, "doc for the last one")
        # lemma statements are normalized to the (semantically identical) theorem keyword
        self.assertTrue(by_name["comp_add"].statement.startswith("theorem comp_add"))
        for t in theorems:
            self.assertEqual(t.namespace, "LinearMap")


class Test_ClaudeCliEnvelope(unittest.TestCase):
    """Parsing of the ``claude -p --output-format json`` envelope (no pyirk state)."""

    def test_ok_envelope_yields_text_and_usage(self):
        payload = {
            "type": "result",
            "is_error": False,
            "result": "OK:\n```python\npass\n```",
            "total_cost_usd": 0.0421,
            "duration_api_ms": 12345,
            "session_id": "abc-123",
            "num_turns": 5,
        }
        res = authoring._parse_claude_cli_json(json.dumps(payload))
        self.assertEqual(res.text, payload["result"])
        self.assertAlmostEqual(res.cost_usd, 0.0421)
        self.assertAlmostEqual(res.duration_api_s, 12.3)
        self.assertEqual(res.session_id, "abc-123")
        self.assertEqual(res.num_turns, 5)

    def test_error_envelope_raises_with_reason(self):
        # the shape the CLI produced when the account session limit was hit
        payload = {"is_error": True, "result": "You've hit your session limit - resets 2:10am"}
        with self.assertRaisesRegex(RuntimeError, "session limit"):
            authoring._parse_claude_cli_json(json.dumps(payload))

    def test_non_json_output_degrades_to_bare_text(self):
        res = authoring._parse_claude_cli_json("plain text, no envelope")
        self.assertEqual(res.text, "plain text, no envelope")
        self.assertIsNone(res.cost_usd)


class Test_FailureClassGuards(unittest.TestCase):
    """Pure-function guards for the run-2 residual failure classes."""

    def test_nonascii_outside_strings_reported_but_labels_ignored(self):
        code = (
            'I1 = p.create_item(R1__has_label="trace ∘ map")\n'  # ∘ in a label
            "y = a ∘ b\n"  # ∘ in actual code
        )
        hits = authoring.find_nonascii_outside_strings(code)
        self.assertEqual([h[2] for h in hits], ["∘"])
        self.assertEqual(hits[0][0], 2)  # line 2, not the label on line 1

    def test_nonascii_none_when_only_in_labels_and_comments(self):
        code = (
            'I1 = p.create_item(R1__has_label="α ↔ β",\n'
            '    R2__has_description="x → y")  # comment with ∀\n'
        )
        self.assertEqual(authoring.find_nonascii_outside_strings(code), [])

    def test_reopened_scope_on_foreign_item_detected(self):
        code = (
            'I5001 = p.create_item(R1__has_label="t")\n'
            'with I5001["t"].scope("setting") as st:\n    pass\n'
            'with I5002["old"].scope("setting") as st:\n    pass\n'
        )
        self.assertEqual(authoring.find_reopened_scopes(code), ["I5002"])

    def test_multiple_scopes_on_block_declared_item_are_ok(self):
        code = (
            'I5001 = p.create_item(R1__has_label="t")\n'
            'with I5001["t"].scope("setting") as st:\n    pass\n'
            'with I5001["t"].scope("premise") as st:\n    pass\n'
            'with I5001["t"].scope("assertion") as st:\n    pass\n'
        )
        self.assertEqual(authoring.find_reopened_scopes(code), [])


class Test_AuthoringCLI(HousekeeperMixin, unittest.TestCase):
    def test_help_lists_new_flags(self):
        help_text = script.create_parser().format_help()
        for flag in (
            "--import-lean",
            "--target",
            "--theorem",
            "--all",
            "--ocse-uri",
            "--ocse-path",
            "--working-uri",
        ):
            self.assertIn(flag, help_text)

    def test_single_theorem_happy_path(self):
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "trivial.lean")

        # Use a temp dir for the auto-generated working module so we never touch
        # the repo tree.
        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_")
        target_path = pjoin(tmpdir, "lean_theorems_work.py")
        self.files_to_delete.append(target_path)

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = lambda *a, **kw: CANNED_OK_BLOCK
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                theorem="foo",
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(target_path))

        # Round-trip: module must be re-loadable via irkloader.
        mod = p.irkloader.load_mod_from_path(target_path, prefix="lt_test", reuse_loaded=False)
        self.assertEqual(mod.__URI__, "irk:/lean_theorems_test/0.1")
        # R9999 was declared by the bootstrap.
        self.assertEqual(mod.R9999.R1.value, "has source reference")
        # The appended theorem item is present.
        self.assertEqual(mod.I7777.R1.value, "trivial identity (1=1)")

    def test_all_flag_iterates_theorems(self):
        """With --all the CLI should iterate every parsed theorem."""
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "two_theorems.lean")

        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_all_")
        # Distinct filename from the happy-path test so the modname does not
        # collide across tests in this class.
        target_path = pjoin(tmpdir, "lean_theorems_all.py")
        self.files_to_delete.append(target_path)

        # Distinct OK blocks per call so the two appended items get distinct keys
        # (re-declaring the same IXXXX would crash the validation re-load).
        ok_block_one = (
            "OK:\n"
            "```python\n"
            "I7001 = p.create_item(\n"
            '    R1__has_label="triv one",\n'
            '    R2__has_description="theorem: 1 equals 1",\n'
            '    R4__is_instance_of=p.I15["implication proposition"],\n'
            '    R9999__has_source_reference="Lean / mathlib4: .triv_one",\n'
            ")\n"
            "```\n"
        )
        ok_block_two = (
            "OK:\n"
            "```python\n"
            "I7002 = p.create_item(\n"
            '    R1__has_label="triv two",\n'
            '    R2__has_description="theorem: 2 equals 2",\n'
            '    R4__is_instance_of=p.I15["implication proposition"],\n'
            '    R9999__has_source_reference="Lean / mathlib4: .triv_two",\n'
            ")\n"
            "```\n"
        )
        queue = [ok_block_one, ok_block_two]
        call_count = {"n": 0}

        def fake_propose(*a, **kw):
            call_count["n"] += 1
            return queue.pop(0)

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = fake_propose
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                all_theorems=True,
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)
        self.assertEqual(call_count["n"], 2)
        self.assertTrue(os.path.exists(target_path))

        with open(target_path) as fp:
            written = fp.read()
        self.assertIn("I7001", written)
        self.assertIn("I7002", written)

        # The final round-trip below intentionally relies on
        # ``reuse_loaded=False`` actually re-executing the file. Before the
        # irkloader fix (dd35721d) a ``sys.modules`` short-circuit returned the
        # stale I7001-only cached module here, so this test used to drop the
        # cache by hand. That manual workaround is gone on purpose: keeping it
        # would *mask* a regression of the underlying bug. If the short-circuit
        # ever comes back, the ``I7002`` assertion below fails.
        mod = p.irkloader.load_mod_from_path(target_path, prefix="lt_test_all", reuse_loaded=False)
        self.assertEqual(mod.I7001.R1.value, "triv one")
        self.assertEqual(mod.I7002.R1.value, "triv two")

    def test_fork_policy_skip_records_pending_and_continues(self):
        """--fork-policy skip must not block on stdin: the forked theorem is
        recorded as fork_pending in --stats-jsonl and the run continues."""
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "two_theorems.lean")

        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_skip_")
        target_path = pjoin(tmpdir, "lean_theorems_skip.py")
        stats_path = pjoin(tmpdir, "stats.jsonl")
        self.files_to_delete.append(target_path)

        fork_block = (
            "FORK:\n" "Q: ambiguous modeling for theorem one?\n" "  (a) option a\n" "  (b) option b\n"
        )
        responses = iter([fork_block, CANNED_OK_BLOCK])

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = lambda *a, **kw: next(responses)
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                all_theorems=True,
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
                fork_policy="skip",
                stats_jsonl=stats_path,
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        # a fork-pending theorem is not a failure
        self.assertEqual(rc, 0)

        with open(stats_path) as fp:
            records = [json.loads(line) for line in fp if line.strip()]
        self.assertEqual([r["outcome"] for r in records], ["fork_pending", "ok"])
        self.assertIn("ambiguous modeling", records[0]["fork_question"])

        # the skipped theorem must not appear in the module, the imported one must
        with open(target_path) as fp:
            written = fp.read()
        self.assertIn("I7777", written)

    def test_resume_skips_recorded_theorems(self):
        """An interrupted --all run is resumable: theorems already recorded in
        --stats-jsonl are skipped, the rest are processed."""
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "two_theorems.lean")

        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_resume_")
        target_path = pjoin(tmpdir, "lean_theorems_resume.py")
        stats_path = pjoin(tmpdir, "stats.jsonl")
        self.files_to_delete.append(target_path)

        ok_block_two = CANNED_OK_BLOCK.replace("I7777", "I7778").replace("(1=1)", "(2=2)")
        calls = {"n": 0}

        def fake_propose(*a, **kw):
            calls["n"] += 1
            return ok_block_two

        # simulate the first (interrupted) run: theorem one already recorded
        theorems = authoring_lean.parse_theorems(open(lean_fixture).read())
        self.assertEqual(len(theorems), 2)
        with open(stats_path, "w") as fp:
            fp.write(
                json.dumps({"theorem": theorems[0].name, "namespace": theorems[0].namespace, "outcome": "ok"})
                + "\n"
            )

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = fake_propose
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                all_theorems=True,
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
                stats_jsonl=stats_path,
                resume=True,
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)
        # only the second theorem may have triggered a propose call
        self.assertEqual(calls["n"], 1)

        with open(stats_path) as fp:
            records = [json.loads(line) for line in fp if line.strip()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["theorem"], theorems[1].name)
        self.assertEqual(records[1]["outcome"], "ok")

    def test_stats_record_tracks_cost_of_inner_calls(self):
        """Per-call usage metadata from propose_via_claude must aggregate into
        the stats record (cost_usd sum + n_claude_calls)."""
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "trivial.lean")

        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_cost_")
        target_path = pjoin(tmpdir, "lean_theorems_cost.py")
        stats_path = pjoin(tmpdir, "stats.jsonl")
        self.files_to_delete.append(target_path)

        # first call malformed (forces a retry), second call OK -- two priced calls
        responses = iter(
            [
                authoring.ClaudeCallResult(text="no parseable structure", cost_usd=0.03),
                authoring.ClaudeCallResult(text=CANNED_OK_BLOCK, cost_usd=0.04),
            ]
        )

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = lambda *a, **kw: next(responses)
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                theorem="foo",
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
                stats_jsonl=stats_path,
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)
        with open(stats_path) as fp:
            records = [json.loads(line) for line in fp if line.strip()]
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["outcome"], "ok")
        self.assertEqual(rec["n_malformed"], 1)
        self.assertEqual(rec["n_claude_calls"], 2)
        self.assertAlmostEqual(rec["cost_usd"], 0.07)
        # the events stream carries the per-call costs
        self.assertEqual([e.get("cost_usd") for e in rec["events"]], [0.03, 0.04])

    def _run_two_response_recovery(self, tmp_prefix, first_block):
        """Helper: first propose response is `first_block` (faulty), second is the
        canonical OK block. Returns the single stats record after a --theorem run."""
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "trivial.lean")
        tmpdir = tempfile.mkdtemp(prefix=tmp_prefix)
        target_path = pjoin(tmpdir, "work.py")
        stats_path = pjoin(tmpdir, "stats.jsonl")
        self.files_to_delete.append(target_path)

        responses = iter(
            [
                authoring.ClaudeCallResult(text=first_block, cost_usd=0.01),
                authoring.ClaudeCallResult(text=CANNED_OK_BLOCK, cost_usd=0.02),
            ]
        )
        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = lambda *a, **kw: next(responses)
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                theorem="foo",
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
                stats_jsonl=stats_path,
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)
        with open(stats_path) as fp:
            records = [json.loads(line) for line in fp if line.strip()]
        self.assertEqual(len(records), 1)
        return records[0]

    def test_nonascii_block_is_reprompted_then_succeeds(self):
        """A code block with a Lean operator outside strings is caught and
        re-prompted, not appended; the retry succeeds and is recorded."""
        bad_block = (
            "OK:\n```python\n"
            "I7777 = p.create_item(\n"
            '    R1__has_label="bad",\n'
            '    R2__has_description="x",\n'
            '    R4__is_instance_of=p.I15["implication proposition"],\n'
            '    R9999__has_source_reference="Lean / mathlib4: .foo",\n'
            ")\n"
            "y = a ∘ b\n"  # stray Lean composition operator in real code
            "```\n"
        )
        rec = self._run_two_response_recovery("pyirk_authoring_cli_nonascii_", bad_block)
        self.assertEqual(rec["outcome"], "ok")
        self.assertEqual(rec["n_nonascii"], 1)
        self.assertEqual(rec["n_claude_calls"], 2)

    def test_scope_reopen_is_reprompted_then_succeeds(self):
        """A `with KEY.scope(...)` on an item not declared in the block is caught
        and re-prompted before it can raise InvalidScopeNameError."""
        bad_block = (
            "OK:\n```python\n"
            "I7777 = p.create_item(\n"
            '    R1__has_label="reopen test",\n'
            '    R2__has_description="x",\n'
            '    R4__is_instance_of=p.I15["implication proposition"],\n'
            '    R9999__has_source_reference="Lean / mathlib4: .foo",\n'
            ")\n"
            'with I3["extended natural number"].scope("setting") as st:\n'
            "    pass\n"
            "```\n"
        )
        rec = self._run_two_response_recovery("pyirk_authoring_cli_reopen_", bad_block)
        self.assertEqual(rec["outcome"], "ok")
        self.assertEqual(rec["n_scope_reopens"], 1)
        self.assertEqual(rec["n_claude_calls"], 2)

    def test_timeout_is_retried_not_fatal(self):
        """A subprocess timeout on the first call is a retryable attempt, not a
        fatal error that kills the theorem."""
        import subprocess as _sp

        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "trivial.lean")
        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_timeout_")
        target_path = pjoin(tmpdir, "work.py")
        stats_path = pjoin(tmpdir, "stats.jsonl")
        self.files_to_delete.append(target_path)

        calls = {"n": 0}

        def fake_propose(*a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _sp.TimeoutExpired(cmd="claude", timeout=kw.get("timeout", 600))
            return authoring.ClaudeCallResult(text=CANNED_OK_BLOCK, cost_usd=0.02)

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = fake_propose
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                theorem="foo",
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
                stats_jsonl=stats_path,
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)
        self.assertEqual(calls["n"], 2)
        with open(stats_path) as fp:
            records = [json.loads(line) for line in fp if line.strip()]
        self.assertEqual(records[0]["outcome"], "ok")
        self.assertEqual(records[0]["n_timeouts"], 1)

    def test_auto_bootstrap_creates_module(self):
        """When --target points at a non-existent file, the CLI bootstraps it."""
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "trivial.lean")

        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_boot_")
        # subdir under tmpdir does NOT pre-exist -- the bootstrap must mkdir -p.
        target_path = pjoin(tmpdir, "fresh", "lean_theorems_boot.py")
        self.files_to_delete.append(target_path)

        self.assertFalse(os.path.exists(target_path))

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = lambda *a, **kw: CANNED_OK_BLOCK
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                theorem="foo",
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_test/0.1",
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(target_path))

        with open(target_path) as fp:
            written = fp.read()
        # bootstrap skeleton + working URI + OCSE wiring
        for needle in (
            "R9999",
            "register_mod",
            "start_mod",
            "end_mod",
            "irk:/lean_theorems_test/0.1",
            "irkloader.load_mod_from_path",
            os.path.abspath(TEST_DATA_PATH_MA),
            # The imported theorem entity from CANNED_OK_BLOCK.
            "I7777",
            "trivial identity (1=1)",
        ):
            self.assertIn(needle, written)

        mod = p.irkloader.load_mod_from_path(target_path, prefix="lt_test_boot", reuse_loaded=False)
        self.assertEqual(mod.__URI__, "irk:/lean_theorems_test/0.1")
        self.assertEqual(mod.I7777.R1.value, "trivial identity (1=1)")

    def test_fork_loop_converges(self):
        """FORK on the first attempt + OK on the second exercises the escalation loop.

        ``script.import_lean`` currently hard-codes ``ask_user_via_stdin``; rather than
        mutate production code, this test drives ``authoring.lean.import_theorem``
        directly -- the substrate piece the CLI delegates to. Acceptable per the task
        description.
        """
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "trivial.lean")

        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_cli_fork_")
        target_path = pjoin(tmpdir, "lean_theorems_fork.py")
        self.files_to_delete.append(target_path)

        # Bootstrap the working module by hand (script.import_lean would normally do this).
        authoring.bootstrap_working_module(
            Path(target_path),
            "irk:/lean_theorems_test/0.1",
            TEST_DATA_PATH_MA,
        )

        session = authoring.Session(working_module_path=Path(target_path), working_module_prefix="")
        session.load_dependency(TEST_DATA_PATH_MA, prefix="ma")

        theorems = authoring_lean.parse_theorems(open(lean_fixture).read())
        self.assertEqual(len(theorems), 1)

        fork_block = (
            "FORK:\n"
            "Q: how should triv be modeled?\n"
            "  (a) introduce a new local item under p.I15\n"
            "  (b) reuse an existing implication entity\n"
        )
        propose_calls = {"n": 0}

        def fake_propose(prompt, **kw):
            propose_calls["n"] += 1
            if propose_calls["n"] == 1:
                return fork_block
            return CANNED_OK_BLOCK

        ask_user_calls = []

        def fake_ask_user(question, options):
            ask_user_calls.append((question, list(options)))
            return "a"

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = fake_propose
        try:
            ok = authoring_lean.import_theorem(
                theorems[0],
                session=session,
                working_module_path=Path(target_path),
                source_url="",
                ask_user=fake_ask_user,
            )
        finally:
            authoring.propose_via_claude = original_propose

        self.assertTrue(ok)
        self.assertEqual(propose_calls["n"], 2)
        self.assertEqual(len(ask_user_calls), 1)
        # the FORK options must have been parsed and forwarded to ask_user
        forwarded_letters = [letter for letter, _ in ask_user_calls[0][1]]
        self.assertIn("a", forwarded_letters)
        self.assertIn("b", forwarded_letters)

        mod = p.irkloader.load_mod_from_path(target_path, prefix="lt_test_fork", reuse_loaded=False)
        self.assertEqual(mod.I7777.R1.value, "trivial identity (1=1)")


class Test_RemapCollidingKeys(unittest.TestCase):
    """Unit tests for ``authoring.remap_colliding_keys`` (pure string manipulation, no pyirk state)."""

    def test_builtin_collision_remapped_everywhere(self):
        """A declared key colliding with a builtin is remapped in assignment and label-reference form."""
        code = (
            "I17 = p.create_item(\n"
            '    R1__has_label="some theorem",\n'
            '    R4__is_instance_of=p.I15["implication proposition"],\n'
            ")\n"
            'with I17["some theorem"].scope("setting") as st:\n'
            "    pass\n"
        )
        # I17 and I18 occupied → I19 is the first free slot
        occupied = {"I17", "I18"}
        new_code, mapping = authoring.remap_colliding_keys(code, occupied)
        self.assertEqual(mapping, {"I17": "I19"})
        self.assertNotIn("I17 =", new_code)
        self.assertIn("I19 =", new_code)
        self.assertNotIn('I17["', new_code)
        self.assertIn('I19["', new_code)
        # the p.I15 builtin reference must not be touched
        self.assertIn("p.I15[", new_code)

    def test_working_module_collision_remapped(self):
        """A key colliding with one already declared in the working module is remapped."""
        code = "I500 = p.create_item(\n" '    R1__has_label="my item",\n' ")\n"
        occupied = {"I500", "I501"}  # I502 is the first free slot
        new_code, mapping = authoring.remap_colliding_keys(code, occupied)
        self.assertEqual(mapping, {"I500": "I502"})
        self.assertIn("I502 =", new_code)
        self.assertNotIn("I500 =", new_code)

    def test_reuse_reference_not_touched(self):
        """A key that appears in the block but is NOT declared there must not be remapped."""
        code = (
            "I900 = p.create_item(\n"
            '    R1__has_label="new item",\n'
            '    R4__is_instance_of=p.I17["equivalence proposition"],\n'
            ")\n"
        )
        # I17 is in occupied but is only referenced (not declared) → no remap
        occupied = {"I17"}
        new_code, mapping = authoring.remap_colliding_keys(code, occupied)
        self.assertEqual(mapping, {})
        self.assertEqual(new_code, code)

    def test_relation_kwarg_form_remapped(self):
        """The kwarg form RKEY__attr= of a declared relation is remapped consistently."""
        code = (
            "R50 = p.create_relation(\n"
            '    R1__has_label="my relation",\n'
            ")\n"
            "I900 = p.create_item(\n"
            '    R1__has_label="my item",\n'
            "    R50__my_relation=some_value,\n"
            ")\n"
        )
        occupied = {"R50", "R51"}  # R52 is the first free slot
        new_code, mapping = authoring.remap_colliding_keys(code, occupied)
        self.assertEqual(mapping, {"R50": "R52"})
        self.assertIn("R52 =", new_code)
        self.assertIn("R52__my_relation=", new_code)
        self.assertNotIn("R50 =", new_code)
        self.assertNotIn("R50__my_relation=", new_code)
        # builtin kwarg R1__has_label must not be affected
        self.assertIn("R1__has_label=", new_code)

    def test_no_collision_returns_identical_code(self):
        """When no key collides, the returned code is byte-identical to the input."""
        code = "I5000 = p.create_item(\n" '    R1__has_label="my item",\n' ")\n"
        occupied = {"I17", "I18"}  # I5000 is not occupied
        new_code, mapping = authoring.remap_colliding_keys(code, occupied)
        self.assertEqual(mapping, {})
        self.assertEqual(new_code, code)


class Test_KeyRemapIntegration(HousekeeperMixin, unittest.TestCase):
    """Integration test: key-collision remapping is wired into the import pipeline."""

    def test_occupied_key_remapped_on_import(self):
        """LLM output declaring I17 (a builtin) is silently remapped; import succeeds with stats."""
        lean_fixture = pjoin(_LOCAL_TEST_DATA, "lean", "trivial.lean")

        tmpdir = tempfile.mkdtemp(prefix="pyirk_authoring_remap_")
        target_path = pjoin(tmpdir, "lean_theorems_remap.py")
        stats_path = pjoin(tmpdir, "stats_remap.jsonl")
        self.files_to_delete.append(target_path)

        # Block deliberately declares I17 -- a builtin entity -- to force a remap.
        collision_block = (
            "OK:\n"
            "```python\n"
            "I17 = p.create_item(\n"
            '    R1__has_label="collision test theorem",\n'
            '    R2__has_description="key-collision remapping integration test",\n'
            '    R4__is_instance_of=p.I15["implication proposition"],\n'
            '    R9999__has_source_reference="test: collision",\n'
            ")\n"
            "```\n"
        )

        original_propose = authoring.propose_via_claude
        authoring.propose_via_claude = lambda *a, **kw: collision_block
        try:
            args = _build_args(
                import_lean=lean_fixture,
                target=target_path,
                theorem="foo",
                ocse_path=TEST_DATA_PATH_MA,
                working_uri="irk:/lean_theorems_remap/0.1",
                stats_jsonl=stats_path,
            )
            rc = script.import_lean(args)
        finally:
            authoring.propose_via_claude = original_propose

        self.assertEqual(rc, 0)

        with open(stats_path) as fp:
            records = [json.loads(line) for line in fp if line.strip()]
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["outcome"], "ok")
        self.assertGreaterEqual(rec["n_key_remaps"], 1)
        # key_remap is not a claude call
        self.assertEqual(rec["n_claude_calls"], 1)

        # There must be a key_remap event with I17 in the mapping
        remap_events = [e for e in rec["events"] if e["event"] == "key_remap"]
        self.assertTrue(remap_events, "expected at least one key_remap event")
        self.assertIn("I17", remap_events[0]["mapping"])

        # The working module must NOT contain the original collision declaration
        with open(target_path) as fp:
            written = fp.read()
        self.assertNotIn("I17 = p.create_item", written)
        self.assertIn("collision test theorem", written)

        # Round-trip: module must be loadable
        mod = p.irkloader.load_mod_from_path(target_path, prefix="lt_remap_test", reuse_loaded=False)
        self.assertEqual(mod.__URI__, "irk:/lean_theorems_remap/0.1")
