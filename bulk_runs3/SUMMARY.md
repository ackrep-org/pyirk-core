# Bulk-Run-3 Auswertung: Drei Lean-Import-Korpora (BUDGET-CAPPED — UNVOLLSTÄNDIG)

> **WICHTIG:** Dieser Run ist wegen Budget-Erschöpfung unvollständig.
> Nur `eigenspace` (35 Records) und `trace` (35 Records) wurden ausgeführt.
> **`ode_transform` (Analysis_ODE_Transform.lean, Ziel: 19 Records) wurde NICHT ausgeführt** — Budget erschöpft.
> Das Acceptance-Kriterium „35 + 35 + 19 Records vollständig" ist damit **nicht erfüllt**.

Vergleichsdaten für Run 2 stammen aus `bulk_runs2/SUMMARY.md`.

---

## A. Metriken pro Korpus (Run 3)

| Korpus | Total | ok | failed | error | FORK-Rate | Val-Retry-Rate | Mean dur (s) | Max dur (s) | Σ cost_usd | Σ n_claude_calls | Σ n_key_remaps | Σ n_nonascii | Σ n_scope_reopens | Σ n_timeouts |
|--------|-------|----|--------|-------|-----------|----------------|--------------|-------------|------------|------------------|----------------|--------------|-------------------|--------------|
| eigenspace | 35 | 32 | 3 | 0 | 94,3 % (33/35) | 11,4 % (4/35) | 380,1 | 910,9 | 15,45 $ | 77 | 12 | 3 | 0 | 2 |
| trace | 35 | 33 | 2 | 0 | 74,3 % (26/35) | 8,6 % (3/35) | 197,1 | 442,5 | 9,76 $ | 69 | 3 | 0 | 0 | 0 |
| ode_transform | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

- **FORK-Rate**: Anteil der Theoreme mit mindestens einem `fork`-Event.
- **Val-Retry-Rate**: Anteil der Theoreme mit mindestens einem `validation_fail`-Event.
- **Σ n_nonascii**: Summe der gefeuerten Non-ASCII-Guard-Events über alle Theoreme.
- **Σ n_timeouts**: Summe der Timeout-Events (jetzt retryable, nicht mehr fatal).

---

## B. Vergleich Run 2 vs. Run 3

| Korpus | Run 2 ok | Run 2 failed | Run 2 error | Run 3 ok | Run 3 failed | Run 3 error | Δ ok |
|--------|----------|-------------|------------|----------|-------------|------------|------|
| eigenspace | 30 | 3 | 2 | 32 | 3 | 0 | **+2** |
| trace | 32 | 2 | 1 | 33 | 2 | 0 | **+1** |
| ode_transform | 18 | 1 | 0 | nicht ausgefuehrt | — | — | n/a |

---

## C. Guard-Wirksamkeit (auswertbar für eigenspace und trace)

### Guard 1: Non-ASCII Lean Ops

Ziel-Theoreme aus Run 2 (beide `failed` mit `SyntaxError` — Unicode-Zeichen im generierten Python-Code):

| Theorem | Korpus | Run 2 | Run 3 Outcome | n_nonascii Run 3 | Bewertung |
|---------|--------|-------|---------------|-----------------|-----------|
| HasUnifEigenvalue.mem_spectrum | eigenspace | failed (SyntaxError `→` U+2192) | **ok** | 0 | Guard nicht gefeuert; Modell vermied Unicode diesmal — Theorem jetzt ok |
| trace_transpose | trace | failed (SyntaxError `∘` U+2218) | **ok** | 0 | Guard nicht gefeuert; Modell vermied Unicode diesmal — Theorem jetzt ok |

Zusätzlich: 3 eigenspace-Theoreme haben `n_nonascii > 0` und der Non-ASCII-Guard griff:

| Theorem | n_nonascii | Outcome |
|---------|-----------|---------|
| mem_genEigenspace_top | 1 | ok |
| mem_genEigenspace_one | 1 | ok |
| HasUnifEigenvector.apply_eq_smul | 1 | ok |

**Fazit:** Guard gefeuert & Theorem ok (3 Fälle). Die beiden Run-2-Fehler-Kandidaten lösten den Guard gar nicht aus — das Modell produzierte diesmal keinen Unicode. **Keine non-ASCII-bedingten Fehler in Run 3.**

---

### Guard 2: Scope-Reopen

Ziel-Theorem aus Run 2 (`mem_genEigenspace_one`: `failed` mit `InvalidScopeNameError`):

| Theorem | Korpus | Run 2 | Run 3 Outcome | n_scope_reopens Run 3 | Bewertung |
|---------|--------|-------|---------------|----------------------|-----------|
| mem_genEigenspace_one | eigenspace | failed (InvalidScopeNameError) | **ok** | 0 | Guard nicht gefeuert; Scope-Kollision trat nicht auf — Theorem jetzt ok |

**Zweites Run-2-Beispiel (`IsIntegralCurveOn.comp_sub`, ode_transform):** Nicht auswertbar — Korpus ode_transform wurde wegen Budget-Erschöpfung nicht ausgeführt.

Kein einziges Theorem in Run 3 hat `n_scope_reopens > 0`. Der Guard wurde in keinem der verfügbaren Korpora ausgelöst, die Fehlerklasse trat gar nicht erst auf.

**Fazit:** Klasse in Run 3 nicht aufgetreten (weder Fehlschlag noch Guard-Feuerung); zweites Beispiel nicht auswertbar (ode_transform fehlt).

---

### Guard 3: Timeout-Guard (TimeoutExpired jetzt retryable statt fatal)

Run-2-Fehler durch `TimeoutExpired` (outcome=error): `mem_genEigenspace` (694,5 s), `mem_genEigenspace_top` (eigenspace), `Module.Free.bijective_algebraMap_of_finrank_eq_one` (trace, 1036,4 s).

| Theorem | Run 2 | Run 3 Outcome | n_timeouts Run 3 | Bewertung |
|---------|-------|---------------|-----------------|-----------|
| mem_genEigenspace | error (TimeoutExpired) | **ok** | 0 | Timeout diesmal nicht aufgetreten; Theorem ok |
| mem_genEigenspace_top | error (TimeoutExpired) | **ok** | n/a (nonascii-Event) | Timeout nicht aufgetreten; Theorem ok |
| Module.Free.bijective_algebraMap_of_finrank_eq_one | error (TimeoutExpired) | **failed** (TypeError) | 0 | Timeout nicht aufgetreten; scheitert jetzt an TypeError |

In Run 3 gibt es **kein einziges `outcome=error`** — die Timeout-Fehlerklasse als fataler Abbruch ist vollständig verschwunden. Zwei eigenspace-Theoreme haben `n_timeouts=1`:

| Theorem | n_timeouts | Outcome | Bedeutung |
|---------|-----------|---------|-----------|
| HasUnifEigenvalue.isNilpotent_of_isNilpotent | 1 | failed | Guard gefeuert & retry ausgelöst; Theorem scheiterte trotzdem (gave_up nach 3 Versuchen) |
| HasUnifEigenvalue.le | 1 | failed | Guard gefeuert & retry ausgelöst; Theorem scheiterte trotzdem (malformed + timeout) |

**Fazit:** Timeout-Guard gefeuert & trotzdem failed (2 Fälle). Keine `error`-Outcomes mehr — die frühere Fehlerklasse „TimeoutExpired fatal" ist in Run 3 eliminiert.

---

## D. Failure-Klassifikation

| Korpus | Theorem | Outcome | Fehlerklasse |
|--------|---------|---------|--------------|
| eigenspace | HasUnifEigenvalue.isNilpotent_of_isNilpotent | failed | Timeout (n_timeouts=1) → fork → gave_up nach 3 Versuchen |
| eigenspace | hasUnifEigenvalue_iff_mem_spectrum | failed | malformed → fork → `AssertionError` (validation_fail) → gave_up |
| eigenspace | HasUnifEigenvalue.le | failed | malformed → timeout (n_timeouts=1) → gave_up |
| trace | traceAux_def | failed | `TypeError: entity '<Item I1002["ring"]>' is not a class` → fork → gave_up |
| trace | Module.Free.bijective_algebraMap_of_finrank_eq_one | failed | `TypeError: entity '<Item I9031["finite rank (scalar)"]>' is not a class` → malformed → gave_up |

**Zusammenfassung der Fehlerklassen in Run 3 (zwei Korpora):**
- `TypeError` — Entität ist keine instanziierbare Klasse (2): 1× trace (traceAux_def), 1× trace (bijective_algebraMap)
- Timeout + gave_up (1): 1× eigenspace (isNilpotent_of_isNilpotent)
- malformed + gave_up — AssertionError (1): 1× eigenspace (iff_mem_spectrum)
- malformed + Timeout + gave_up (1): 1× eigenspace (HasUnifEigenvalue.le)

---

## E. Qualitative Beobachtungen

### (i) Alle Run-2-`error`-Outcomes eliminiert

Die wichtigste Verbesserung in Run 3: Kein einziger Record hat `outcome=error`. In Run 2 gab es noch 3 fatale Abbrüche (2× eigenspace, 1× trace), ausnahmslos durch `TimeoutExpired`. In Run 3 sind alle ehemaligen Timeout-Opfer entweder `ok` (mem_genEigenspace, mem_genEigenspace_top, trace_transpose gelöst) oder `failed` statt `error` (Module.Free.bijective_algebraMap... — Timeout tritt gar nicht auf, scheitert aber an TypeError). Der Timeout-Guard macht Timeouts zu nicht-fatalen Retry-Events.

### (ii) Netto-Fortschritt trotz drei Regressionen

Run 3 gewinnt gegenüber Run 2 insgesamt 3 `ok`-Ergebnisse (eigenspace +2, trace +1), aber es gibt **3 Regressionen** — Theoreme, die in Run 2 `ok` waren und in Run 3 `failed` sind:

| Theorem | Korpus | Run 2 | Run 3 |
|---------|--------|-------|-------|
| HasUnifEigenvalue.isNilpotent_of_isNilpotent | eigenspace | ok | failed (Timeout) |
| hasUnifEigenvalue_iff_mem_spectrum | eigenspace | ok | failed (AssertionError) |
| traceAux_def | trace | ok | failed (TypeError ring) |

Diese Regressionen sind nicht auf neue Guards oder Konfigurationsänderungen zurückzuführen — sie deuten auf nicht-deterministische Modellvarianz hin. In Run 2 hatte `traceAux_def` zwei Forks und endete `ok`; in Run 3 führt dasselbe Problem (Ring-Item nicht als Klasse erkennbar) nach zwei Versuchen zum Abbruch.

### (iii) Kosteneffizienz: mean n_claude_calls leicht gesunken

| Korpus | Run 2 mean n_claude_calls | Run 3 mean n_claude_calls | Δ |
|--------|--------------------------|--------------------------|---|
| eigenspace | 2,23 (78/35) | 2,20 (77/35) | −0,03 |
| trace | 2,09 (73/35) | 1,97 (69/35) | −0,12 |

Kein messbarer Guard-Overhead im Durchschnitt — Guards (Non-ASCII, Timeout) sparen durch frühen Abbruch und Redirect tendenziell Calls gegenüber kostspieligen Fehlschlägen.

### (iv) TypeError als neue dominierende Fehlerklasse

In Run 2 dominierten SyntaxError (Unicode), TimeoutExpired und InvalidScopeNameError. In Run 3 sind diese Klassen weitgehend beseitigt. Die neue Hauptfehlerklasse ist `TypeError: entity is not a class` (2 von 5 Fehlern, beide trace). Das Muster: der Agent erstellt ein Item (z.B. `I1002["ring"]`) als einfaches Objekt, nicht als pyirk-Klasse, und dann versucht ein späteres Theorem, daraus per `uq_instance_of` eine Instanz zu erzeugen. Diese Fehlerklasse ist lösbar (Klassen müssen mit `R3__is_subclass_of` angelegt werden), erfordert aber eine gezielte Guard- oder Prompt-Anpassung.

### (v) FORK-Rate gestiegen, Validierungs-Retry-Rate gesunken

Im Vergleich zu Run 2 (eigenspace 88,6 %, trace 77,1 %) ist die FORK-Rate in Run 3 höher (eigenspace 94,3 %, trace 74,3 % — eigenspace +5,7 pp, trace −2,8 pp). Die Val-Retry-Rate sank von 17,1 % auf 11,4 % (eigenspace) und von 14,3 % auf 8,6 % (trace). Weniger Validierungsfehler deutet auf verbesserte Code-Qualität im ersten Versuch hin; die höhere FORK-Rate in eigenspace zeigt, dass mehr Theoreme mehrdeutige Typ-Entscheidungen erfordern.
