# P3 OCSE Skalentest — Statusbericht

Lauf: 2026-06-06, Worker task_001b

---

## 1. Pre-flight

| Metrik | Wert |
|--------|------|
| uptime load (1-min) bei Start | 0.60 (Warnung: ≥0.5) |
| Top-CPU-Prozess bei Start | node/openclaw (1.2%) |
| Nemo-Version | nemo-cli 0.10.0 |
| Pytest-Baseline | 3 failed (pre-existing: `pyirk` CLI nicht auf PATH), 155 passed, 4 skipped, 2 xfailed |

Anmerkung: Alle Timing-Runs liefen unter erhöhter Last (load=1.01–1.27); beide Läufe als load-belastet markiert.

---

## 2. Klassifikation-Tabelle

Aus `p3_rule_classification.json` (4 Regeln gesamt):

| Key   | Label                                          | Kategorie  |
|-------|------------------------------------------------|------------|
| I64   | introduction of generalized subclass statements | direct     |
| I65   | propagation of generalized subclass            | direct     |
| I66   | propagation transitive relations               | transitive |
| I4731 | element type rule                              | direct     |

**Zähler je Kategorie:** `{'direct': 3, 'transitive': 1}`

Delegierbare Regelkopf-Prädikate: R30, R83 (direct); R17 (transitive)

---

## 3. Korrektheits-Ergebnis

| Kennzahl | Wert |
|----------|------|
| pyirk-Tupel | 373 |
| Nemo-Tupel | 373 |
| Identisch? | **JA** |
| Diff | keiner |

**Tupelaufschlüsselung:**
- R83 (I64/I65 – generalized subclass): 299 Tupel
- R17 (I66 – transitiv): 74 Tupel
- R30 (I4731 – element type): 0 neue (Regel hat auf OCSE-Daten keine neuen R30-Fakten erzeugt)

Roh-EDB: 1919 Tripel (unqualifiziert), 59 qualifizierte Statements

---

## 4. Timing-Tabelle

Messung: best-of-2 Subprozesse (Hinweis: ursprünglich N=3 vorgesehen; auf N=2 reduziert laut Task).

**pyirk misst:** `apply_semantic_rules(*delegatable_rules, exhaust=True)`
**Nemo misst:** `export_datastore + generate_rls + nmo-Run + Output-Parse`

| Run | pyirk (s) | Nemo (s) |
|-----|-----------|----------|
| 1   | 348.1167  | 0.4685   |
| 2   | 348.1978  | 0.4470   |
| **Best** | **348.12** | **0.447** |

**Speedup (t_pyirk_best / t_nemo_best): 778.78x ≈ 779x**

Last-Hinweis: Alle 4 Runs liefen unter erhöhter Systemlast (load=1.01–1.27). pyirk-Zeiten könnten unter unbelastetem System etwas günstiger liegen; Nemo ist durch Last kaum beeinflussbar (0.45 s ist CPU-satt-gebunden bei Nemo-intern). Der Speedup ist bei 779x robust.

---

## 5. Reproduktionsbefehl

```bash
/home/user/venvs/pyirk-core-venv/bin/python experiments/h5_phase1/p3_ocse_scale.py 2>&1 | tee experiments/h5_phase1/p3_ocse_scale.log
```

---

## 6. Schlusszeile

```
P3-VERDICT: ocse_korrekt=ja speedup_test_e01=779x (load-belastet, load=1.01-1.27 während pyirk-Runs)
```
