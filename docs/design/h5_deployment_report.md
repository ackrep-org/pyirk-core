# H5 Deployment — Abschlussbericht: Robuste Auflösung, Fallback-Politik, Akzeptanz-Gate

> Branch: `h5_deployment` · Stand: 2026-06-12 · Code-Commit: `db4f6576`

---

## 1. Zusammenfassung der Änderungen

Diese Iteration härtet die in `h5_phase2` und `h5_extension` aufgebaute
Nemo-Delegation für den Deployment-Kontext (Container, fremde
Entwicklerrechner, CI). Der funktionale Umfang der Delegation bleibt
unverändert; verändert wurde nur, wie das `nmo`-Binary aufgelöst wird,
wie Versions-Inkompatibilitäten erkannt werden, und wie Warnungen sich
über die Lebenszeit eines Prozesses verhalten.

Kern-Änderungen, Code-Commit `db4f6576`
(`feat(nemobridge): robust nmo resolver, idempotent warnings, version check`):

* **Robuste Binary-Auflösung** in `src/pyirk/nemobridge/delegation.py`:
  neue Funktion `_resolve_nmo_bin()` mit der Reihenfolge
  `PYIRK_NEMO_BIN` → `shutil.which("nmo")` → Legacy-Default
  `/home/user/bin/nmo` → `None`. Erste existierende Datei gewinnt.
* **Idempotente Warnungen** über Modul-State-Flags
  (`_resolver_logged`, `_warned_no_binary`, `_warned_nmo_failed`,
  `_warned_version_mismatch`). Jede Fehlerart genau eine
  `logger.warning`-Zeile pro Prozess; exportiert als
  `mark_nmo_failed_warned()` für den `ruleengine`-Hook.
* **Gecachter Versions-Check** über `functools.lru_cache(maxsize=1)`
  in `_check_nmo_version(nmo_bin)` — `nmo --version` läuft einmal pro
  Prozess.
* **Minimal-invasiver Hook** in `src/pyirk/ruleengine.py`: +5 / −3 Zeilen,
  die den bereits bestehenden Delegations-Aufruf an die neuen
  Resolver-/Versions-Helfer anbinden und im Fehlerfall sauber auf den
  nativen Pfad zurückfallen lassen.
* **17 neue Unit-Tests** in `tests/test_nemobridge_resolver.py`, organisiert
  in sechs Test-Klassen: `TestResolverOrder`, `TestResolverLogging`,
  `TestHookFallbackNoBinary`, `TestBrokenBinaryFallback`,
  `TestVersionCheckMatrix`, `TestMarkNmoFailedWarned`.

Default-Verhalten ist unverändert: das Flag `PYIRK_NEMO_DELEGATION` bleibt
**aus**, das `nmo`-Binary wird **nicht** mit pyirk ausgeliefert.

---

## 2. Resolver-Strategie

```text
PYIRK_NEMO_BIN  →  shutil.which("nmo")  →  /home/user/bin/nmo  →  None
   (if exists)        (PATH lookup)       (legacy host default)
```

Implementierung: `src/pyirk/nemobridge/delegation.py::_resolve_nmo_bin`.

* `PYIRK_NEMO_BIN` zählt nur, wenn die env-Variable gesetzt **und** der
  referenzierte Pfad existiert; eine falsch gesetzte Variable verhindert
  also nicht das Fallback auf `PATH`.
* `shutil.which("nmo")` ist der reguläre Pfad in CI und auf
  Entwicklerrechnern mit Standard-Installation.
* Der Legacy-Default `/home/user/bin/nmo` bleibt als drittes Glied, weil
  das die historische Installation auf der Mess-Maschine war. Er greift
  nur, wenn die Datei existiert — Container ohne diesen Pfad ignorieren
  ihn lautlos.
* Bleibt am Ende `None`, schaltet der Hook auf nativen Fallback um und
  protokolliert genau eine Warning (siehe Abschnitt 3).

Pro Prozess wird genau eine `logger.info`-Zeile geschrieben, z.B.
`nmo binary resolved via shutil.which: /usr/local/bin/nmo`, gesteuert
über das Flag `_resolver_logged`. Damit ist aus jedem Log unmittelbar
ablesbar, welcher Kandidat tatsächlich verwendet wurde.

---

## 3. Fallback-Strategie & Atomizität

Drei Fehler-Klassen sind explizit abgedeckt; jede erzeugt genau **eine**
`logger.warning`-Zeile pro Prozess und führt zum nativen Pfad:

1. **Kein Binary auffindbar** → `_warn_no_binary_once()` (Flag
   `_warned_no_binary`).
2. **Versions-Inkompatibilität** (major mismatch / unparseable / RC≠0)
   → `_check_nmo_version(...)` schreibt eine Warning und gibt `False`
   zurück (Flag `_warned_version_mismatch`).
3. **Subprocess-Fehler oder CSV-Parse-Fehler zur Laufzeit** →
   `mark_nmo_failed_warned(exc)` (Flag `_warned_nmo_failed`), exportiert,
   damit der Hook in `ruleengine.apply_semantic_rules` denselben
   Idempotenz-Pfad nutzen kann.

**Atomizität:** Subprocess- bzw. CSV-Parse-Failures werfen im
Delegations-Pfad einen `RuntimeError`, **bevor** irgendeine
`DataStore`-Mutation stattfindet. Die mutierende Stage
`_materialize_tuples` ist konstruktiv die *letzte* im
Delegations-Aufruf — wird sie nicht erreicht, bleibt der `DataStore`
exakt im Zustand vor dem Versuch. Damit ist auch ein abgebrochener
Delegations-Versuch frei von halb-geschriebenen Statements und der
native Re-Run startet auf einem konsistenten Substrat.

---

## 4. Versions-Politik

`_check_nmo_version(nmo_bin)` vergleicht den vom Binary über
`nmo --version` gemeldeten Triplet `MAJOR.MINOR.PATCH` gegen die
validierte Reihe `0.10.x`.

| Diskrepanz                       | Verhalten           | Begründung |
|---|---|---|
| Patch (`0.10.y`)                 | ok, keine Warnung   | Patch-Releases ändern den CLI- und RLS-Codegen-Vertrag nicht. |
| Minor (`0.11.z` etc.)            | 1× Warning, *warn + try* | 0.x-Minor-Bumps sind erfahrungsgemäß häufig additiv; ein Hook-Failure führt automatisch zum nativen Fallback — kein Datenverlust, Performance-Gewinn falls kompatibel. |
| Major (`1.x.y` etc.)             | 1× Warning, Fallback | Major-Bumps brechen verlässlich Verträge (CLI-Flags, Output-Format). Ein Versuch lohnt sich nicht. |
| Unparseable / RC ≠ 0             | 1× Warning, Fallback | Kein verlässliches Signal über die Version — sicher bleiben, native Engine nutzen. |

Der Subprocess `nmo --version` ist über
`functools.lru_cache(maxsize=1)` gecacht: pro Prozess (und pro
`nmo_bin`-Pfad) genau ein Aufruf, unabhängig davon, wie viele
Rule-Engine-Runs folgen.

---

## 5. Akzeptanz-Gate — Belege

Alle Gates wurden in task_002 im Branch `h5_deployment` gegen
Code-Commit `db4f6576` gefahren; die Rohlogs liegen unter
`experiments/h5_deployment/`. Die folgenden Kennzahlen sind wörtlich aus
diesen Logs übernommen.

### 5.1 Gate-1 — volle Suite, Flag AUS

* Log: `experiments/h5_deployment/gate1_full_flag_off.log`
* Befehl (vgl. `experiments/h5_deployment/gate_summary.md`):
  `env -u PYIRK_NEMO_DELEGATION pytest -p no:randomly`
* Ergebnis: **189 passed, 4 skipped, 2 xfailed, 3 failed** (`+1 error`
  beim Teardown derselben CLI-Test-Klasse).
* Die drei Failures stammen aus `tests/test_script.py` und scheitern an
  `sh: 1: pyirk: not found` — Exitcode 32512 entspricht
  `127 << 8` (Shell-Exitcode 127 = *command not found*).
* **Honest-Stop-Klausel:** Diese Failures sind orthogonal zur
  Nemo-Delegation. Beleg: `experiments/h5_deployment/which_pyirk.log`
  enthält wörtlich `NOT_ON_PATH` — die `pyirk`-CLI ist im Container
  schlicht nicht installiert; die fehlgeschlagenen Tests rufen sie via
  `os.system("pyirk ...")` auf. Kein Regress aus diesem Branch.

### 5.2 Gate-2 — `test_rulebased_reasoning.py`, Flag AN

* Log: `experiments/h5_deployment/gate2_rulebased_flag_on.log`
* Befehl: `PYIRK_NEMO_DELEGATION=1 pytest tests/test_rulebased_reasoning.py -p no:randomly`
* Ergebnis: **24 passed, 4 skipped** in 15.65 s. Keine Failures, keine
  Errors.

### 5.3 Gate-3 — h5_phase2 Equivalence Gate

* Log: `experiments/h5_deployment/gate3_phase2.log`
* Befehl: `python experiments/h5_phase2/equivalence_gate.py`
* Ergebnis (wörtlich aus dem Log):
  * `overall_gate_ok: true`
  * `gate_1_state_equivalent: true (diff_subjects=0)`
  * `gate_2_idempotent: true (extra_stmts_on_replay=0)`
  * `gate_3_dup_equiv_native: true (diff_triples=0, native_dups=5, deleg_dups=5)`
  * `t_native_sec: 320.9294`, `t_delegation_sec: 1.8295`
  * `speedup_fullrun: 175.42x`

### 5.4 Gate-4 — h5_extension Equivalence Gate

* Log: `experiments/h5_deployment/gate4_extension.log`
* Befehl: `python experiments/h5_extension/equivalence_gate.py`
* Ergebnis (wörtlich aus dem Log):
  * `overall_gate_ok: true`
  * `gate_1_state_equivalent: true (diff_subjects=0)`
  * `gate_2_idempotent: true (extra_native=0, extra_delegation=0)`
  * `gate_3_dup_equiv_native: true (diff_triples=0, native_dups=0, deleg_dups=0)`
  * `t_native_sec: 1.4853`, `t_delegation_sec: 1.1023`
  * `speedup_fullrun: 1.35x`

---

## 6. Negativ-Test-Belege

Die Robustheits-Eigenschaften aus Abschnitten 2-4 sind in
`tests/test_nemobridge_resolver.py` (17 Tests) abgedeckt. Besonders
relevant für die Deployment-Frage sind zwei Test-Klassen:

* **`TestHookFallbackNoBinary`** — Flag AN, aber `_resolve_nmo_bin`
  liefert `None`: belegt, dass der Hook genau **eine** Warning emittiert
  und sauber auf den nativen Pfad zurückfällt, ohne dass eine
  `nmo`-Subprozess-Ausführung versucht wird.
* **`TestBrokenBinaryFallback`** — Flag AN, `nmo`-Binary existiert,
  liefert aber Garbage / RC ≠ 0: belegt, dass der Engine-Aufruf nicht
  crasht und das R1001-Pair-Set vor und nach dem Lauf identisch ist —
  *keine* Datenkorruption durch einen abgebrochenen Delegations-Versuch.

Die verbleibenden Klassen (`TestResolverOrder`, `TestResolverLogging`,
`TestVersionCheckMatrix`, `TestMarkNmoFailedWarned`) decken die
Auflösungs-Reihenfolge, das `logger.info`-Verhalten, die Versions-Matrix
(patch/minor/major/unparseable) und die Idempotenz der
`mark_nmo_failed_warned`-Funktion ab.

---

## 7. Honest-Stop

Die in Gate-1 dokumentierten 3 Failures in `tests/test_script.py`
(`test_a01__insert_keys`, `test_c01__visualization`,
`test_c02__visualization_commands`, plus ERROR im Teardown derselben
Klasse) sind **pre-existing** und werden in diesem Bericht offen
ausgewiesen statt das Gate weichzuschreiben. Sie sind orthogonal zur
Delegation (Beleg: `which_pyirk.log` = `NOT_ON_PATH`) und nicht im
Scope dieser Iteration. Eine Behebung wäre eine separate
Container-/Setup-Frage (Installation der `pyirk`-CLI im Test-Image)
und gehört nicht in den Delegations-Branch.

---

H5DEPLOY-VERDICT: gate_ok=ja
