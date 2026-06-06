# P4 Integration Notes — PYIRK_NEMO_DELEGATION Feature-Flag

## Aktivierung

```bash
PYIRK_NEMO_DELEGATION=1 python ...
```

Ohne dieses Flag: exakt bisheriges Verhalten (Python-Engine, kein Nemo-Aufruf).

## Stiller Fallback

Greift automatisch bei:
- fehlendem Nemo-Binary (`/home/user/bin/nmo`, überschreibbar via `PYIRK_NEMO_BIN`)
- jeder Exception aus dem Delegationspfad (inkl. Phase-1-`NotImplementedError`)

Kein Log-Spam beim fehlenden Binary; `logger.warning` nur bei unerwarteter Exception.

## Reihenfolge (bei aktivem Flag)

1. **Nemo-Block**: delegierbare Regeln (Kategorie `direct` + `transitive`) → Nemo bis Fixpunkt
2. **Python-Block**: restliche Regeln (`python_only`, SPARQL, OR-Subscope) → Python-Engine wie bisher

## Bekannte Limitationen

- **Rückkopplung nicht umgesetzt**: python_only-Ergebnisse, die delegierbare Regeln erneut
  triggern würden, sind ignoriert. → Phase-2-Thema.
- **CSV→Statement-Mapping fehlt** (Phase-2-TODO): `_apply_via_nemo()` führt Export → RLS →
  `nmo`-Aufruf aus, bricht aber mit `NotImplementedError` ab bevor Statements erzeugt werden.
  Konsequenz: mit PYIRK_NEMO_DELEGATION=1 wird der Nemo-Lauf versucht, aber stiller Fallback
  auf Python-Engine greift immer (Phase 1). Der Hook-Code selbst (Klassifikation, Export,
  nmo-Aufruf) wird vollständig durchlaufen und ist testbar.

## Hook-Stelle

`src/pyirk/ruleengine.py:77` — Beginn des Nemo-Delegationsblocks in `apply_semantic_rules()`.

Hilfsfunktionen in `src/pyirk/nemobridge/delegation.py`:
- `_nemo_available()` — Binary-Check
- `_split_rules_by_nemo_delegation(rules)` — Klassifikation via `classify_rules`
- `_apply_via_nemo(delegated_rules, mod_context_uri)` — Pipeline (Phase 1: Skeleton)

## Test

`tests/test_nemobridge_integration.py` — Smoke-Test:
- `test_nemo_delegation_flag_smoke` (skipif kein `nmo`): prüft, dass Flag-Pfad keinen
  unkontrollierten Absturz verursacht und Fallback korrekte Ergebnisse liefert.
- `test_nemo_delegation_flag_off_unchanged`: prüft, dass Default-Pfad (kein Flag) unberührt ist.
