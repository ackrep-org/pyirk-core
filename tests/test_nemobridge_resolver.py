"""
Unit tests for pyirk.nemobridge.delegation — deployment-robustness layer
(H5 Deployment, task_001):

  * ``_resolve_nmo_bin()`` — precedence ``PYIRK_NEMO_BIN`` → ``shutil.which``
    → legacy default ``~/bin/nmo`` (expanded) → ``None``; logs the chosen
    source exactly once per process.
  * Idempotent warnings: ``_warned_no_binary``, ``_warned_nmo_failed``,
    ``_warned_version_mismatch`` — each fires at most one log record per
    process even across many calls.
  * ``_check_nmo_version()`` policy matrix: ``0.10.x`` ok silently;
    ``0.11.0`` warn + try (returns True); ``1.0.0`` warn + fallback
    (returns False); unparseable warn + fallback (returns False).
  * Hook-level integration: with the flag on but the resolver returning
    ``None``, ``apply_semantic_rules`` falls back to the native engine,
    emits exactly one warning over multiple calls, and produces the same
    result as the native path. With a stubbed ``subprocess.run``
    simulating a broken nmo at the version-check stage, the hook never
    enters the delegation path and the DataStore stays untouched by
    delegation.

None of these tests require a real nmo binary — all subprocess calls
that would normally exec nmo are monkey-patched.
"""

import logging
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
_SPIKE_DIR = os.path.join(REPO_ROOT, "experiments", "h5_spike")
if _SPIKE_DIR not in sys.path:
    sys.path.insert(0, _SPIKE_DIR)

import pyirk as p  # noqa: E402
from pyirk import ruleengine  # noqa: E402
from pyirk.nemobridge import delegation  # noqa: E402
from create_test_kb import setup_test_module, TEST_MOD_URI  # noqa: E402


# ── shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_delegation_state(monkeypatch):
    """Reset module-level idempotency flags and the version cache per test.

    Without this, a test that legitimately emits one warning would change
    the cross-test count for the next test and tests would couple in
    surprising ways.
    """
    monkeypatch.setattr(delegation, "_resolver_logged", False)
    monkeypatch.setattr(delegation, "_warned_no_binary", False)
    monkeypatch.setattr(delegation, "_warned_nmo_failed", False)
    monkeypatch.setattr(delegation, "_warned_version_mismatch", False)
    delegation._check_nmo_version.cache_clear()
    yield
    delegation._check_nmo_version.cache_clear()


def _records_for(caplog, level, needle):
    """Return caplog records matching *needle* in the message at the given level."""
    return [
        r for r in caplog.records
        if r.levelno == level and needle in r.getMessage()
    ]


# ── A) Resolver-Reihenfolge ──────────────────────────────────────────────────

class TestResolverOrder:

    def test_env_var_wins_when_path_exists(self, monkeypatch, tmp_path):
        env_bin = tmp_path / "env_nmo"
        env_bin.write_text("")
        # shutil.which would otherwise find something; we still want env_var to win.
        other = tmp_path / "path_nmo"
        other.write_text("")
        monkeypatch.setenv("PYIRK_NEMO_BIN", str(env_bin))
        monkeypatch.setattr(delegation.shutil, "which",
                            lambda name: str(other) if name == "nmo" else None)
        assert delegation._resolve_nmo_bin() == str(env_bin)

    def test_env_var_ignored_when_path_missing(self, monkeypatch, tmp_path):
        # Env points to a non-existent file → falls through to next candidates.
        which_bin = tmp_path / "path_nmo"
        which_bin.write_text("")
        monkeypatch.setenv("PYIRK_NEMO_BIN", str(tmp_path / "absent"))
        monkeypatch.setattr(delegation.shutil, "which",
                            lambda name: str(which_bin) if name == "nmo" else None)
        assert delegation._resolve_nmo_bin() == str(which_bin)

    def test_falls_through_to_shutil_which(self, monkeypatch, tmp_path):
        which_bin = tmp_path / "path_nmo"
        which_bin.write_text("")
        monkeypatch.delenv("PYIRK_NEMO_BIN", raising=False)
        monkeypatch.setattr(delegation.shutil, "which",
                            lambda name: str(which_bin) if name == "nmo" else None)
        assert delegation._resolve_nmo_bin() == str(which_bin)

    def test_falls_through_to_legacy_default(self, monkeypatch, tmp_path):
        default_bin = tmp_path / "legacy_nmo"
        default_bin.write_text("")
        monkeypatch.delenv("PYIRK_NEMO_BIN", raising=False)
        monkeypatch.setattr(delegation.shutil, "which", lambda name: None)
        monkeypatch.setattr(delegation, "_LEGACY_DEFAULT_NMO_BIN", str(default_bin))
        assert delegation._resolve_nmo_bin() == str(default_bin)

    def test_returns_none_when_nothing_found(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PYIRK_NEMO_BIN", raising=False)
        monkeypatch.setattr(delegation.shutil, "which", lambda name: None)
        monkeypatch.setattr(delegation, "_LEGACY_DEFAULT_NMO_BIN",
                            str(tmp_path / "definitely-not-here"))
        assert delegation._resolve_nmo_bin() is None


# ── B) Resolver log line exactly once ────────────────────────────────────────

class TestResolverLogging:

    def test_info_emitted_exactly_once_over_many_calls(
        self, monkeypatch, tmp_path, caplog,
    ):
        default_bin = tmp_path / "legacy_nmo"
        default_bin.write_text("")
        monkeypatch.delenv("PYIRK_NEMO_BIN", raising=False)
        monkeypatch.setattr(delegation.shutil, "which", lambda name: None)
        monkeypatch.setattr(delegation, "_LEGACY_DEFAULT_NMO_BIN", str(default_bin))

        caplog.set_level(logging.INFO, logger="pyirk.nemobridge.delegation")
        for _ in range(7):
            delegation._resolve_nmo_bin()

        msgs = _records_for(caplog, logging.INFO, "nmo binary resolved")
        assert len(msgs) == 1, (
            f"expected exactly one INFO log line, got {[r.getMessage() for r in msgs]}"
        )

    def test_info_says_not_found_when_nothing_resolves(
        self, monkeypatch, tmp_path, caplog,
    ):
        monkeypatch.delenv("PYIRK_NEMO_BIN", raising=False)
        monkeypatch.setattr(delegation.shutil, "which", lambda name: None)
        monkeypatch.setattr(delegation, "_LEGACY_DEFAULT_NMO_BIN",
                            str(tmp_path / "absent"))
        caplog.set_level(logging.INFO, logger="pyirk.nemobridge.delegation")
        for _ in range(3):
            delegation._resolve_nmo_bin()
        msgs = _records_for(caplog, logging.INFO, "no candidate found")
        assert len(msgs) == 1


# ── C) Missing binary → hook falls back, one warning ─────────────────────────

class TestHookFallbackNoBinary:
    """Flag on, no binary found anywhere → exactly one warning + native path."""

    def setup_method(self):
        self.entities = setup_test_module()

    def teardown_method(self):
        p.unload_mod(TEST_MOD_URI, strict=False)

    def test_hook_falls_back_silently_after_first_warning(
        self, monkeypatch, tmp_path, caplog,
    ):
        # Make sure no nmo binary is resolvable.
        monkeypatch.delenv("PYIRK_NEMO_BIN", raising=False)
        monkeypatch.setattr(delegation.shutil, "which", lambda name: None)
        monkeypatch.setattr(delegation, "_LEGACY_DEFAULT_NMO_BIN",
                            str(tmp_path / "absent"))
        monkeypatch.setenv("PYIRK_NEMO_DELEGATION", "1")

        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")

        # Two calls — the warning must only fire once total.
        res1 = ruleengine.apply_semantic_rules(p.I64, mod_context_uri=TEST_MOD_URI)
        res2 = ruleengine.apply_semantic_rules(p.I64, mod_context_uri=TEST_MOD_URI)

        # Native fallback produced statements at least on the first call.
        assert len(res1.new_statements) > 0, (
            "native fallback should produce R83 statements on the first pass"
        )
        # res2 may be a no-op on a saturated KB; key is no crash + no extra warning.
        assert res2 is not None

        warns = _records_for(
            caplog, logging.WARNING, "no nmo binary could be located",
        )
        assert len(warns) == 1, (
            f"expected exactly one no-binary warning across two calls, got "
            f"{[r.getMessage() for r in warns]}"
        )


# ── D) Broken binary at runtime → fallback, no partial state ─────────────────

class TestBrokenBinaryFallback:
    """Subprocess stub returns garbage → version check fails → fallback,
    no DataStore mutation from the delegation path."""

    def setup_method(self):
        self.entities = setup_test_module()

    def teardown_method(self):
        p.unload_mod(TEST_MOD_URI, strict=False)

    def _r1001_pairs(self):
        rel_uri = self.entities["R1001"].uri
        out = set()
        for _subj_uri, rel_dict in p.ds.statements.items():
            stm_or_list = rel_dict.get(rel_uri)
            if stm_or_list is None:
                continue
            stms = stm_or_list if isinstance(stm_or_list, list) else [stm_or_list]
            for stm in stms:
                s, o = stm.subject, stm.object
                if hasattr(s, "short_key") and hasattr(o, "short_key"):
                    out.add((s.short_key, o.short_key))
        return out

    def test_subprocess_exit_1_raises_runtimeerror_without_mutating(
        self, monkeypatch, tmp_path,
    ):
        """Direct call to ``_apply_via_nemo`` with a broken subprocess →
        RuntimeError; no statements were added."""
        fake_bin = tmp_path / "broken_nmo"
        fake_bin.write_text("")
        monkeypatch.setenv("PYIRK_NEMO_BIN", str(fake_bin))

        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="boom",
            )
        monkeypatch.setattr(delegation.subprocess, "run", fake_run)

        before = self._r1001_pairs()
        with pytest.raises(RuntimeError, match="nmo exit"):
            delegation._apply_via_nemo([p.I66], TEST_MOD_URI)
        after = self._r1001_pairs()
        assert after == before, (
            "broken-subprocess delegation must not mutate the DataStore"
        )

    def test_hook_falls_back_when_version_check_fails(
        self, monkeypatch, tmp_path, caplog,
    ):
        """Stub the version-check subprocess to return garbage → version
        check returns False → hook never enters delegation; native fallback
        runs; one warning total even across two calls."""
        fake_bin = tmp_path / "garbage_nmo"
        fake_bin.write_text("")
        monkeypatch.setenv("PYIRK_NEMO_BIN", str(fake_bin))
        monkeypatch.setenv("PYIRK_NEMO_DELEGATION", "1")

        def fake_run(cmd, **kw):
            # nmo --version → returncode 0, but no parseable version in output.
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="not a version string", stderr="",
            )
        monkeypatch.setattr(delegation.subprocess, "run", fake_run)

        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        before = self._r1001_pairs()
        ruleengine.apply_semantic_rules(p.I64, mod_context_uri=TEST_MOD_URI)
        ruleengine.apply_semantic_rules(p.I64, mod_context_uri=TEST_MOD_URI)
        after = self._r1001_pairs()

        # Delegation never ran → R1001 closure not materialised (native pass
        # only touches R83 / I64-derived statements).
        assert after == before, (
            "version-check failure must not lead to delegation-side mutations"
        )

        warns = _records_for(
            caplog, logging.WARNING, "Could not parse nmo version",
        )
        assert len(warns) == 1, (
            f"expected exactly one version-parse warning, got "
            f"{[r.getMessage() for r in warns]}"
        )


# ── E) Versions-Check-Matrix ─────────────────────────────────────────────────

def _stub_version_output(monkeypatch, stdout, returncode=0):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout=stdout, stderr="",
        )
    monkeypatch.setattr(delegation.subprocess, "run", fake_run)


class TestVersionCheckMatrix:

    def test_patch_difference_is_silently_ok(self, monkeypatch, caplog):
        _stub_version_output(monkeypatch, "nmo 0.10.5")
        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        assert delegation._check_nmo_version("/fake/nmo") is True
        warns = _records_for(caplog, logging.WARNING, "nmo version")
        assert warns == [], f"patch difference must not warn, got {warns}"

    def test_minor_mismatch_warns_but_returns_true(self, monkeypatch, caplog):
        _stub_version_output(monkeypatch, "nmo 0.11.0")
        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        assert delegation._check_nmo_version("/fake/nmo") is True
        warns = _records_for(caplog, logging.WARNING, "MINOR")
        assert len(warns) == 1

    def test_major_mismatch_warns_and_returns_false(self, monkeypatch, caplog):
        _stub_version_output(monkeypatch, "nmo 1.0.0")
        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        assert delegation._check_nmo_version("/fake/nmo") is False
        warns = _records_for(caplog, logging.WARNING, "MAJOR")
        assert len(warns) == 1

    def test_unparseable_warns_and_returns_false(self, monkeypatch, caplog):
        _stub_version_output(monkeypatch, "totally unrelated output")
        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        assert delegation._check_nmo_version("/fake/nmo") is False
        warns = _records_for(caplog, logging.WARNING, "Could not parse")
        assert len(warns) == 1

    def test_subprocess_raises_warns_and_returns_false(self, monkeypatch, caplog):
        def boom(cmd, **kw):
            raise FileNotFoundError(cmd[0])
        monkeypatch.setattr(delegation.subprocess, "run", boom)
        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        assert delegation._check_nmo_version("/fake/nmo") is False
        warns = _records_for(caplog, logging.WARNING, "Could not invoke")
        assert len(warns) == 1

    def test_version_warning_is_idempotent(self, monkeypatch, caplog):
        """Repeated _check_nmo_version calls on the same path → cached;
        warning never fires twice."""
        _stub_version_output(monkeypatch, "nmo 1.0.0")
        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        for _ in range(5):
            assert delegation._check_nmo_version("/fake/nmo") is False
        warns = _records_for(caplog, logging.WARNING, "MAJOR")
        assert len(warns) == 1


# ── F) mark_nmo_failed_warned() idempotency ──────────────────────────────────

class TestMarkNmoFailedWarned:

    def test_fires_only_once_across_many_calls(self, caplog):
        caplog.set_level(logging.WARNING, logger="pyirk.nemobridge.delegation")
        for i in range(4):
            delegation.mark_nmo_failed_warned(RuntimeError(f"call {i}"))
        warns = _records_for(caplog, logging.WARNING, "Nemo delegation failed")
        assert len(warns) == 1
