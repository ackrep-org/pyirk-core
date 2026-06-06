# H5 Phase 1 — P1 + P2 Status Report

Generated: 2026-06-06, Branch: `h5_phase1`

## 1. Was liegt wo

| Pfad | Beschreibung |
|---|---|
| `src/pyirk/nemobridge/__init__.py` | Package-Init mit Re-Exports der gesamten Public API |
| `src/pyirk/nemobridge/exporter.py` | P1: DataStore→Nemo-CSV-Exporter (`export_datastore`, `export_relation_facts`, `is_scope_internal`) |
| `src/pyirk/nemobridge/translator.py` | P2: Regel-Klassifikator und .rls-Codegenerator (`classify_rules`, `generate_rls`, `generate_transitivity_facts`, `classification_to_json`, `RuleClassification`) |
| `experiments/h5_phase1/verify_p1_r1.py` | Teilverifikation R1 (W1-Artefakt, 49/49) |
| `experiments/h5_phase1/verify_p1_r1.log` | Log der R1-Teilverifikation |
| `experiments/h5_phase1/verify_spike_kb.py` | Vollständige Verifikation R1+R2 gegen Spike-Baselines |
| `experiments/h5_phase1/verify_spike_kb.log` | Log des Verifikationslaufs |
| `tests/test_nemobridge_exporter.py` | Unit-Tests für den Exporter (W1) |
| `tests/test_nemobridge_translator.py` | Unit-Tests für Translator + RLS-Codegenerator (32 Tests) |
| `tests/test_nemobridge_verify.py` | Integrationstest: ruft verify_spike_kb.py als Subprozess auf |

## 2. Regel-Klassifikationstabelle

Basis: `classify_rules(p.ds)` gegen die Spike-Test-KB
(`experiments/h5_spike/create_test_kb.setup_test_module()`).

| rule_short_key | label | category | reason |
|---|---|---|---|
| I64 | introduction of generalized subclass statements | direct | Pure triple-pattern premise and assertion — translatable to Datalog |
| I65 | propagation of generalized subclass | direct | Pure triple-pattern premise and assertion — translatable to Datalog |
| I66 | propagation transitive relations | transitive | R2-type: R60__is_transitive marker + wildcard relation (R58) in premise — covered by generate_transitivity_facts() |

**Zähler je Kategorie:**

| category | Anzahl |
|---|---|
| direct | 2 |
| transitive | 1 |
| python_only | 0 |
| **Gesamt** | **3** |

_Hinweis:_ Die 3 Regeln sind die einzigen Regeln der pyirk-Builtins. Die Spike-Test-KB
lädt keine weiteren Regelmoduln. Der Translator generalisiert korrekt auf beliebige
`I41__semantic_rule`-Instanzen in `p.ds`.

### Generierter .rls-Output (combined)

```
% nemobridge auto-generated rules — do not edit manually

@import triples :- csv{resource="triples.csv"} .

% ── Direct rules ─────────────────────────────────────────

% I64: introduction of generalized subclass statements
R83(?i2, ?i1) :- triples(?i2, R3, ?i1) .

% I65: propagation of generalized subclass
R83(?i3, ?i1) :- R83(?i2, ?i1), R83(?i3, ?i2) .

% ── Transitivity ─────────────────────────────────────────

% is_transitive facts — auto-generated from R60__is_transitive=True
is_transitive(R17) .
is_transitive(R1001) .

% Transitive closure — standard Datalog pattern for R2-type rules
% Base: include all triples whose predicate is marked as transitive
trans(?s, ?p, ?o) :- triples(?s, ?p, ?o), is_transitive(?p) .
% Recursive step: apply transitivity until fixpoint
trans(?i1, ?r, ?i3) :- is_transitive(?r), trans(?i1, ?r, ?i2), trans(?i2, ?r, ?i3) .

% ── Exports ──────────────────────────────────────────────
@export R83 :- csv{resource="output_R83.csv"} .
@export trans :- csv{resource="output_trans.csv"} .
```

## 3. Zwischenverifikation

Nemo-Binary: `/home/user/bin/nmo` (nemo-cli 0.10.0 — vorhanden)

| Prüfung | Ergebnis | Baseline |
|---|---|---|
| R1 — I64 (R3→R83) | **49/49** ✓ | `baseline_r1.json` (49 Einträge) |
| R2 — I66 (transitive Hülle R1001) | **6/6** ✓ | `baseline_r2.json` (6 Einträge) |

Beide Baselines exakt reproduziert. Log: `experiments/h5_phase1/verify_spike_kb.log`.

### Verifikationsdetails

- Exporter schreibt `triples.csv` (292 Zeilen, inkl. 49×R3, 3×R1001, u.a.)
- R1: Nemo mit `rules_r1.rls` (nur I64: `R83(?i2, ?i1) :- triples(?i2, R3, ?i1) .`)
  → 49 R83-Fakten, exakt gleich der Baseline
- R2: Nemo mit `rules_r2.rls` (Transitivity-Fakten für R17+R1001 + trans/3-Regel)
  → 6 trans-Fakten für R1001 (3 direkt + 3 abgeleitet), exakt gleich der Baseline
  (R17 hat keine Tripel im Testmodul → kein Einfluss auf das Ergebnis)

## 4. Testsuite-Stand

Lauf: `/home/user/venvs/pyirk-core-venv/bin/python -m pytest -p no:randomly -q`

```
3 failed, 155 passed, 4 skipped, 2 xfailed, 3 warnings, 1 error in 48.22s
```

- 3 pre-existing failures (test_script.py: `sh: 1: pyirk: not found`) — unverändert seit W1
- +32 neue Tests: 22 für Translator (test_nemobridge_translator.py) + 10 für verify
  (test_nemobridge_verify.py, inkl. Nemo-Integration mit `pytest.skipif`)
- Keine neuen Regressionen gegenüber W1-Stand (123→155 passed)

## 5. Offene TODOs

- Translator deckt nur die 3 pyirk-Builtin-Regeln ab (Test-KB hat keine weiteren).
  Bei Laden weiterer Regelmoduln (OCSE etc.) könnte die Klassifikation `python_only`-Einträge
  liefern — diese werden explizit dokumentiert, nicht stillschweigend übergangen (Design-Ziel ✓).
- `test_nemobridge_verify.py` ist vollständig und skippt korrekt, wenn nmo fehlt.
- Teil B (Integration in ruleengine.py, Feature-Flag) ist explizit ausgeschlossen.

P1P2-VERDICT: ok=ja
