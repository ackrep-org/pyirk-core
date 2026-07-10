# Akzeptanz-Gate H5 Deployment — Zusammenfassung

**Datum:** 2026-06-12
**Branch:** `h5_deployment`
**Head-Commit:** `db4f65761379856b9fec83de9c9278e1029f1054`
**venv:** `/home/user/venvs/pyirk-core-venv`

## Ergebnistabelle

| Gate | Befehl | Ergebnis | Log-Pfad | Kennzahl |
|---|---|---|---|---|
| 1 | `env -u PYIRK_NEMO_DELEGATION pytest -p no:randomly` | **PASS\*** | `experiments/h5_deployment/gate1_full_flag_off.log` | 189 passed, 4 skipped, 2 xfailed, 3 pre-existing failed, 1 error |
| 2 | `PYIRK_NEMO_DELEGATION=1 pytest tests/test_rulebased_reasoning.py -p no:randomly` | **PASS** | `experiments/h5_deployment/gate2_rulebased_flag_on.log` | 24 passed, 4 skipped |
| 3 | `python experiments/h5_phase2/equivalence_gate.py` | **PASS** | `experiments/h5_deployment/gate3_phase2.log` | `overall_gate_ok: true`, speedup_fullrun 175.42x |
| 4 | `python experiments/h5_extension/equivalence_gate.py` | **PASS** | `experiments/h5_deployment/gate4_extension.log` | `overall_gate_ok: true`, speedup_fullrun 1.35x |

Beide Gate-Skripte schreiben kein separates JSON; Ergebnisse liegen vollstaendig in den oben referenzierten Log-Dateien.

## Gate-1 PASS*-Vorbehalt (Pre-Existing-Klausel)

Alle drei in Gate-1 fehlgeschlagenen Tests stammen aus `tests/test_script.py` und scheitern, weil das CLI-Skript `pyirk` auf dem PATH des Containers nicht installiert ist. Sie testen das CLI-Verhalten via `os.system("pyirk ...")` und sind kein Regress aus dem Delegations-Branch.

**`which pyirk`-Output:** `NOT_ON_PATH` (siehe `experiments/h5_deployment/which_pyirk.log`).

**Failed Tests:**
- `tests/test_script.py::Test_01_Script::test_a01__insert_keys`
- `tests/test_script.py::Test_01_Script::test_c01__visualization`
- `tests/test_script.py::Test_01_Script::test_c02__visualization_commands` (zusaetzlich `ERROR` beim Teardown derselben Klasse)

**Beleg aus dem Log** (Captured stderr, jeweils identisch fuer alle drei Tests):

```
sh: 1: pyirk: not found
```

Exemplarisch Test `test_c01__visualization`:

```
cmd = "pyirk -vis I12"
res = os.system(cmd)
>   self.assertEqual(res, 0)
E   AssertionError: 32512 != 0
```

`32512 = 127 << 8` — Shell-Exitcode 127 entspricht "command not found". Damit ist nachgewiesen, dass die Ursache ausschliesslich die fehlende CLI-Installation im Container ist und nicht das Delegations-Feature. Honest-Stop-Klausel: die fehlende CLI-Installation gehoert nicht in den Scope dieses Gates und wird offen dokumentiert statt das Gate aufzuweichen.

## Diagnose Gates 2-4

Keine. Alle Gates 2-4 grun, `overall_gate_ok: true` in 3 und 4.

## Gesamtergebnis

Alle vier Gates erfuellt (3x PASS, 1x PASS* mit dokumentiertem Pre-Existing-Vorbehalt). Damit ist die Akzeptanz-Bedingung aus `.orchester/goal.md` Abschnitt "Akzeptanz-Gate" Punkte 1-3 erfuellt; Punkte 4 (Negativ-Tests) und 5 (Bericht) verbleiben fuer task_003.
