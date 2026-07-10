"""
Integration test: PYIRK_NEMO_DELEGATION feature-flag hook in ruleengine.

Tests laufen mit oder ohne Nemo-Binary.  Der Smoke-Test ist auf Maschinen
ohne nmo-Binary per skipif deaktiviert.

Phase-1-Hinweis: _apply_via_nemo() endet mit NotImplementedError (CSV→Statement-
Mapping ist Phase-2-TODO). Der try/except im Delegationspfad fängt das ab und
fällt auf die Python-Engine zurück. Der Smoke-Test prüft daher:
  - kein unkontrollierter Crash,
  - Ergebnis ist eine ReportingMultiRuleResult-Instanz,
  - Fallback liefert korrekte Python-Ergebnisse (R83-Statements erzeugt).
"""

import os
import sys
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
NEMO_BIN = os.environ.get("PYIRK_NEMO_BIN", "/home/user/bin/nmo")

# Spike-KB importieren (enthält I64/I65-Regeln, die als 'direct' klassifiziert werden)
_SPIKE_DIR = os.path.join(REPO_ROOT, "experiments", "h5_spike")
sys.path.insert(0, _SPIKE_DIR)
from create_test_kb import setup_test_module, TEST_MOD_URI  # noqa: E402

import pyirk as p
from pyirk import ruleengine
from pyirk.ruleengine import ReportingMultiRuleResult


@pytest.mark.skipif(
    not os.path.exists(NEMO_BIN),
    reason=f"nmo binary not available at {NEMO_BIN}",
)
def test_nemo_delegation_flag_smoke(monkeypatch):
    """Mit gesetztem Flag läuft apply_semantic_rules ohne unkontrollierten Absturz
    durch. Phase 1: NotImplementedError aus _apply_via_nemo() löst stillen Fallback
    aus — Ergebnis entspricht dem Python-Pfad."""
    monkeypatch.setenv("PYIRK_NEMO_DELEGATION", "1")

    entities = setup_test_module()
    try:
        # I64 ist eine 'direct'-Regel — wird als delegierbar klassifiziert.
        # Erwartung: Delegation wird versucht, NotImplementedError → stiller Fallback,
        # Python-Engine erzeugt R83-Statements.
        res = ruleengine.apply_semantic_rules(
            p.I64,
            mod_context_uri=TEST_MOD_URI,
        )

        assert res is not None
        assert isinstance(res, ReportingMultiRuleResult), (
            f"Erwartete ReportingMultiRuleResult, bekam {type(res)}"
        )
        # Fallback muss mind. einen R83-Statement erzeugt haben
        assert len(res.new_statements) > 0, (
            "apply_semantic_rules mit I64 sollte R83-Statements erzeugen"
        )
    finally:
        p.unload_mod(TEST_MOD_URI, strict=False)


def test_nemo_delegation_flag_off_unchanged():
    """Ohne gesetztes Flag verhält sich apply_semantic_rules exakt wie vorher."""
    # Flag sicherstellen, dass es nicht gesetzt ist
    os.environ.pop("PYIRK_NEMO_DELEGATION", None)

    entities = setup_test_module()
    try:
        res = ruleengine.apply_semantic_rules(
            p.I64,
            mod_context_uri=TEST_MOD_URI,
        )

        assert res is not None
        assert isinstance(res, ReportingMultiRuleResult)
        assert len(res.new_statements) > 0, "I64 sollte R83-Statements erzeugen"
    finally:
        p.unload_mod(TEST_MOD_URI, strict=False)
