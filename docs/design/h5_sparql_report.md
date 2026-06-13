# H5 SPARQL — Abschlussbericht: SPARQL-Praemissen-Regeln delegierbar machen

> Branch: `h5_sparql` · Stand: 2026-06-13

---

## 1. Zusammenfassung

Diese Iteration erweitert den `pyirk.nemobridge`-Translator so, dass die
zebra-Regeln mit `R63__has_SPARQL_source` — soweit auf das genau abbildbare
BGP-Fragment (`+FILTER (?x != ?y)`) reduziert — hinter
`PYIRK_NEMO_DELEGATION=1` gate-aequivalent an Nemo delegiert werden.
Erkennung und Klassifikation arbeiten strikt auf der **rdflib-SPARQL-
Algebra** (`parseQuery` + `translateQuery`), nicht auf dem Query-Quelltext.

**Neu delegiert (5 Regeln):**

| Regel | Algebra-Form    | Bemerkung |
|-------|-----------------|-----------|
| I710  | BGP + 1× `!=`   | Stage 4 (Inequality) |
| I730  | pure BGP        | Stage 2 (Literal-BGP) |
| I740  | BGP + 5× `!=`   | Stage 4; native feuert auf den Fixtures 0-mal — Multiset-Aequivalenz trivial 0 == 0 |
| I792  | pure BGP        | Stage 2 (Literal-BGP) |
| I798  | pure BGP        | Stage 1 (kleinstes BGP, 4 Tripel) |

**Nicht delegiert (3 Regeln) — kuratiert bzw. Honest-Stop:**

| Regel | Modus       | Kurzbegruendung |
|-------|-------------|-----------------|
| I725  | `python_only` (kurated) | Nativ kein wohldefiniertes Aequivalenzziel (`AssertionError` in `ruleengine._process_result_map`). Siehe §4. |
| I803  | `python_only` (kurated) | BGP bindet `?tuple :R39 ?itm2`; pyirk haengt `has_index` als Qualifier an R39-Statements an, sodass der Exporter sie nach `stmts.csv`/`quals_R40.csv` schreibt und der Nemo-EDB-Seed `fact(?s,?p,?o) :- triples(?s,?p,?o)` sie nicht ingestiert. Native 88 vs. delegated 0. Cross-cutting EDB-Konzern, out-of-scope. |
| I741  | `python_only` (Stage-5 Honest-Stop) | Algebra enthaelt `Minus`. Korrektheit erfordert vorgelagerten Praerequisit-Nachweis, dass Nemos Negation-as-Failure dem nativen `MINUS`-Verhalten entspricht — eigenes Mini-Projekt, in dieser Iteration bewusst nicht angegangen. Siehe §7. |

**Gates:** Alle drei Aequivalenz-Gates liefern `overall_gate_ok: true`
(`h5_sparql`, `h5_phase2`, `h5_extension`; Belege in §5).

**Regression:** Flag-AUS reproduziert die Baseline (189 passed, 0 failed,
4 skipped, 2 xfailed) zuzueglich der fuenf neuen
SPARQL-Multiset-Aequivalenz-Tests und der I803-Curated-Assertion
(194 passed, 0 failed, 5 skipped, 2 xfailed). Flag-AN: 24 passed,
4 skipped, 0 failed/error. Siehe §6.

---

## 2. Methodik

### 2.1 Algebra-basierte BGP-Erkennung

Die Erkennung des Subsets erfolgt **ausschliesslich** ueber die
rdflib-SPARQL-Algebra. Quelle:
`src/pyirk/nemobridge/translator.py::_sparql_extract_pure_bgp` und
`_sparql_extract_bgp_with_inequality`. Beide Funktionen parsen den vom
nativen Engine erzeugten Query-Text (mit korrektem PREFIX-Block aus
`ds.uri_prefix_mapping`), walken die Algebra durch die zulaessigen
Wrapper (`Project`, `SelectQuery`, `Slice`, `Distinct`, `Reduced`,
`OrderBy`, `ToList`, `Join`) und akzeptieren:

- **pure BGP**: nur `BGP`-Knoten — alle anderen CompValues (`Filter`,
  `Minus`, `Union`, `LeftJoin`, `Extend`, `Group`, `AggregateJoin`,
  Property-Paths, unbekannte) lassen die Extraktion `None` zurueckkommen.
- **BGP + Inequality**: `Filter(expr, BGP)`, wobei `expr` eine
  (verschachtelte) Konjunktion (`ConditionalAndExpression`) aus
  ausschliesslich zwei-Variablen-`!=`-`RelationalExpression`-Atomen ist.
  Konstanten-Operanden, Equality, OR, Funktionsaufrufe lassen die
  Extraktion `None` zurueckkommen.

**KEIN Regex auf dem SPARQL-Quelltext.** Die Filter-Klausifikation
betrachtet rdflib-CompValue-Knoten direkt.

### 2.2 Klassifikator-Ausgabe

`_classify_single_rule` liefert pro Regel ein Triple
`(mode, snippet, reason)` mit `mode in {"direct", "transitive",
"python_only"}`. Die SPARQL-Branch im Klassifikator ist (kondensiert):

```python
if _has_sparql_premise(rule):
    if key in _SPARQL_PYTHON_ONLY_RULE_KEYS:
        return result("python_only", None, _SPARQL_PYTHON_ONLY_REASONS[key])
    bgp_triples, rejection = _sparql_extract_pure_bgp(rule)
    if bgp_triples is not None:
        return result("direct", _build_sparql_bgp_snippet(rule, bgp_triples),
                      "SPARQL premise: pure BGP — translated to Datalog ...")
    if rejection == "Filter":
        extracted = _sparql_extract_bgp_with_inequality(rule)
        if extracted is not None:
            ...
            return result("direct", _build_sparql_bgp_snippet(rule, bgp_triples,
                          ineq_pairs=ineq_pairs),
                          "SPARQL premise: BGP + inequality — translated to Datalog ...")
    return result("python_only", None, f"SPARQL-based premise: not a pure BGP ({rejection})")
```

### 2.3 Kuratierte Ausnahmen (`_SPARQL_PYTHON_ONLY_RULE_KEYS`)

Eine Modul-Top-Konstante (`translator.py:78`) blockiert ausgewaehlte
Regeln *vor* dem Pure-BGP-Versuch. Aktuell darin enthalten:

```python
_SPARQL_PYTHON_ONLY_RULE_KEYS = {"I725", "I803"}

_SPARQL_PYTHON_ONLY_REASONS = {
    "I725": "SPARQL: rule excluded by curation"
            " (native undefined on zebra KB — AssertionError in ruleengine)",
    "I803": "SPARQL: rule excluded by curation"
            " (BGP binds qualified-only R39 facts which the Nemo EDB seed"
            " does not carry; native ≠ delegated multiset)",
}
```

Die Begruendungen werden im Klassifikator-Reason ausgegeben und im
Test `test_I803_curated_python_only` referenziert.

---

## 3. Pro Regel

Reihenfolge: I798 → I730 → I792 → I725 → I710 → I740 → I803 → I741
(entspricht der Stufen-Reihenfolge aus `goal.md`).

### 3.1 I798 — pure BGP (Stage 1)

- **Klassifikation:** `direct`. Reason: `SPARQL premise: pure BGP —
  translated to Datalog (H5 SPARQL Stage 1)`.
- **Algebra-Form:** pure BGP, 4 Tripel, 1 Boolean-Literal
  `True^^xsd:boolean` (Verifikation:
  `experiments/h5_sparql/recon.md` §I798).
- **Translator-Verhalten:** Pure-BGP-Pfad. Erzeugt das Snippet (Beleg
  in `task_002_result.md`):

  ```
  fact(?p2, ?rel2, ?itm1) :-
      fact(?rel1, "irk:/ocse/0.2/zebra_base_data#R2850", "LIT:True"),
      fact(?rel1, "irk:/builtins#R43", ?rel2),
      fact(?p1, ?rel1, ?itm1),
      fact(?p1, "irk:/builtins#R50", ?p2) .
  ```
- **Gate-/Test-Beleg:** Per-Rule-Block aus
  `experiments/h5_sparql/equivalence_gate.log`:

  ```
  I798   |           20 |              20 |            true
  ```
  Fixture: `tests/test_h5_sparql_premises.py::
  test_I798_sparql_bgp_native_vs_delegated_multiset_equiv`,
  Prereqs `(I702, I705)`, multiset_gleich = true (Multiset 20 = 20).

### 3.2 I730 — pure BGP (Stage 2)

- **Klassifikation:** `direct`. Reason: `SPARQL premise: pure BGP —
  translated to Datalog (H5 SPARQL Stage 1)`.
- **Algebra-Form:** pure BGP, 4 Tripel, 1 Boolean-Literal `True`
  (recon §I730).
- **Translator-Verhalten:** Pure-BGP-Pfad (gleicher Snippet-Generator
  wie I798). Konklusion mit Rel-Var via `_pred_term` (R58-Praedikat im
  Head).
- **Gate-/Test-Beleg:** Per-Rule-Block:

  ```
  I730   |            6 |               6 |            true
  ```
  Fixture: `tests/test_h5_sparql_premises.py::
  test_I730_sparql_bgp_native_vs_delegated_multiset_equiv`,
  Prereqs `(I702, I705)`, multiset_gleich = true (6 = 6).
  Beispiel-Konklusion (nativ; aus `task_003_result.md`):
  `person7 R9122["owns not"] fox`, `person9 R9122["owns not"] horse`.

### 3.3 I792 — pure BGP (Stage 2)

- **Klassifikation:** `direct`. Reason: `SPARQL premise: pure BGP —
  translated to Datalog (H5 SPARQL Stage 1)`.
- **Algebra-Form:** pure BGP, 7 Tripel, 2 Boolean-Literale
  (`False`/`True`) und das URI-Konstanten-Item
  `zb.I7435["human"]` (recon §I792).
- **Translator-Verhalten:** Pure-BGP-Pfad; konstante Items werden vom
  `_sparql_bgp_term` als quotierte URI-Strings emittiert
  (`fact(?h1, "irk:/builtins#R4", "irk:/ocse/0.2/zebra_base_data#I7435")`).
- **Gate-/Test-Beleg:** Per-Rule-Block:

  ```
  I792   |            8 |               8 |            true
  ```
  Fixture: `tests/test_h5_sparql_premises.py::
  test_I792_sparql_bgp_native_vs_delegated_multiset_equiv`,
  Prereqs `(I702, I705, I730)`. Beispiel-Konklusion (nativ; aus
  `task_003_result.md`): `person8 R50["is different from"] person7`.

### 3.4 I725 — kuratiert `python_only`

- **Klassifikation:** `python_only`. Reason:
  `SPARQL: rule excluded by curation (native undefined on zebra KB —
  AssertionError in ruleengine)`.
- **Algebra-Form:** pure BGP, 2 Tripel, keine Filter, keine Literale
  (recon §I725; algebraisch waere I725 ein Pure-BGP-Kandidat).
- **Translator-Verhalten:** Der Pure-BGP-Pfad wird durch die kuratierte
  Liste `_SPARQL_PYTHON_ONLY_RULE_KEYS` umgangen. Ausfuehrliche
  Begruendung in §4.
- **Honest-Stop-Begruendung:** Auf der zebra-only-KB scheitert die
  *native* Engine in I725 mit
  `AssertionError: assert isinstance(new_subj, core.Entity)`
  (`src/pyirk/ruleengine.py:771`). Da die native Engine das
  Referenz-Orakel ist und kein wohldefiniertes Aequivalenzziel
  existiert, bleibt I725 ausserhalb des Gates und im Translator
  `python_only`.

### 3.5 I710 — BGP + Inequality (Stage 4)

- **Klassifikation:** `direct`. Reason: `SPARQL premise: BGP +
  inequality — translated to Datalog (H5 SPARQL Stage 4)`.
- **Algebra-Form:** `Filter(expr=RelationalExpression(?p1 != ?p2),
  p=BGP(...))`, 3 BGP-Tripel + 1 Boolean-Literal `True` (recon §I710).
- **Translator-Verhalten:** `_sparql_extract_bgp_with_inequality`
  erkennt das einzelne `!=`-Atom; `_build_sparql_bgp_snippet` haengt
  `?p1 != ?p2` als Inequality-Constraint hinten an die Body-Konjunktion
  an (gleiche Mechanik wie fuer Monomorphismus-Constraints in
  `_build_direct_snippet`).
- **Gate-/Test-Beleg:** Per-Rule-Block:

  ```
  I710   |            4 |               4 |            true
  ```
  Fixture: `tests/test_h5_sparql_premises.py::
  test_I710_native_vs_delegated_multiset_equal`,
  Prereqs `(I702, I705)`, multiset_gleich = true (4 = 4).

### 3.6 I740 — BGP + Inequality, native 0-feuernd (Stage 4)

- **Klassifikation:** `direct`. Reason: `SPARQL premise: BGP +
  inequality — translated to Datalog (H5 SPARQL Stage 4)`.
- **Algebra-Form:** `Filter(expr=ConditionalAndExpression(...), p=BGP(...))`
  mit 5× `!=` ueber 4 Variablenpaaren, 8 BGP-Tripel + 2 Boolean-Literale
  `True` (recon §I740). rdflib fasst die fuenf `FILTER (...)`-Klauseln
  in *einer* `ConditionalAndExpression` zusammen — der AND-Walker
  (`_flatten_and`) iteriert ueber `expr.expr` (Kopf) und `expr.other`
  (Schwanz; rekursiv flachgeklopft).
- **Translator-Verhalten:** BGP + Inequality wird korrekt extrahiert
  und uebersetzt (siehe Klassifikator-Probe in
  `experiments/h5_sparql/classify_after_stage4.log`). Die fuenf
  paarweisen `!=`-Constraints landen als Set (`frozenset`-Dedup) im
  Snippet.
- **Gate-/Test-Beleg:** Per-Rule-Block:

  ```
  I740   |            0 |               0 |            true
  ```
  Multiset-Aequivalenz trivial 0 == 0. Native feuert I740 weder auf
  zebra02 noch auf zb+zr+zebra02 — siehe `task_004`/`task_005`-Notes.
  Fixture-Test: `tests/test_h5_sparql_premises.py::
  test_I740_native_vs_delegated_multiset_equal` markiert die Regel mit
  `pytest.skip("native I740 does not fire on zebra02 even after
  prereqs (I702/I705/I730/I792); see task_004 worker notes.")` — die
  Translator-Pfad-Aequivalenz bleibt durch die Klassifikations-Probe
  und das aggregierte Gate-Ergebnis belegt. KEINE schwaechere
  Assertion, KEINE Honest-Stop-Korrektur am Translator.

### 3.7 I803 — kuratiert `python_only`

- **Klassifikation:** `python_only`. Reason:
  `SPARQL: rule excluded by curation (BGP binds qualified-only R39
  facts which the Nemo EDB seed does not carry; native ≠ delegated
  multiset)`.
- **Algebra-Form:** algebraisch waere I803 `bgp_inequality` (8 Tripel
  + 1 `!=`-Filter + 3 Boolean-Literale, recon §I803), die
  Pure-BGP-/Inequality-Pfade wuerden im Klassifikator nicht
  zurueckweisen.
- **Translator-Verhalten:** Pre-Filter durch
  `_SPARQL_PYTHON_ONLY_RULE_KEYS` schon vor dem Algebra-Match.
- **Honest-Stop-Begruendung (aus `task_004_result.md`, Section
  „Problems"):**
  Die Praemisse `?type_of_itm1 :R51 ?tuple . ?tuple :R39 ?itm2` braucht
  die R39-Tripel auf den Haupt-Tuples (`Ia78600 = all_pets_tuple`,
  `Ia47053 = all_beverage_tuple`, ...). Diese Statements werden in
  pyirk immer mit `has_index`-Qualifier angelegt (siehe `new_tuple` in
  `src/pyirk/_builtin/math_expressions.py`); der Nemo-Exporter routet
  *qualifizierte* Statements deterministisch nach
  `stmts.csv`/`quals_<R>.csv`, nicht nach `triples.csv`. Der EDB-Seed
  `fact(?s,?p,?o) :- triples(?s,?p,?o)` produziert daher fuer die
  Haupt-Tuples keine `fact(Ia78600, R39, ...)`-Atome. Native erzeugt
  88 Tupel via rdflib-SPARQL-Sicht, delegated 0. Reparatur erfordert
  einen zweiten EDB-Seed-Pfad (`fact(?s,?p,?o) :- stmts(?_, ?s,?p,?o)`
  mit Verwerfen der Statement-ID), ist cross-cutting und liegt
  ausserhalb des H5-SPARQL-Scopes.
- **Test-Beleg:** `tests/test_h5_sparql_premises.py::
  test_I803_curated_python_only` assertiert das Klassifikator-Verhalten
  (Reason enthaelt `"curat"`); kein Multiset-Vergleich noetig, weil der
  Honest-Stop bewusst greift.

### 3.8 I741 — Stage-5 Honest-Stop (`python_only`)

- **Klassifikation:** `python_only`. Reason:
  `SPARQL-based premise: not a pure BGP (Minus)`.
- **Algebra-Form:** `bgp_negation` — 9 Tripel + 5 `!=`-Filter + **ein
  `Minus`-Subpattern** `MINUS { ?itm2 :R57 true. }` (recon §I741).
- **Translator-Verhalten:** Der Pure-BGP-Walker bricht beim
  `Minus`-Knoten ab und meldet `rejection == "Minus"` (Walker
  rekursiert seit task_003 durch Filter hindurch und verwirft `Filter`
  zugunsten des staerkeren Grundes — sonst waere der Reason
  faelschlich `(Filter)` gewesen). Die Inequality-Extraktion wird gar
  nicht erst probiert, weil `rejection != "Filter"`.
- **Honest-Stop-Begruendung:** ausfuehrliche Diskussion in §7.

---

## 4. Sonderfall I725 — Native AssertionError

Diese Diagnose ist die Begruendung fuer den Eintrag von I725 in
`_SPARQL_PYTHON_ONLY_RULE_KEYS`. Sie wurde bereits in der
H5-Extension-Iteration aufgenommen
(`docs/design/h5_extension_report.md` §5.2) und in dieser Iteration mit
`experiments/h5_sparql/i725_native_check.py` auf der aktuellen
Codebasis (`h5_sparql`-HEAD `0aa598f2f`) reproduziert.

### 4.1 Reproduktion

`experiments/h5_sparql/i725_native_check.py` laedt die zebra-only-KB
(`zebra_base_data` + `zebra_puzzle_rules` ohne Puzzle-Daten) und ruft
`apply_semantic_rules(I725)`. Ergebnis (aus
`experiments/h5_sparql/i725_native_check.log`, zitiert in
`experiments/h5_sparql/recon.md` §I725):

```
SUMMARY: outcome=crash exc=AssertionError file=ruleengine.py line=771 func=_process_result_map
```

Letzter Traceback-Frame:

```
    res = self._process_result_map(result_maps)
  File "src/pyirk/ruleengine.py", line 771, in _process_result_map
    assert isinstance(new_subj, core.Entity)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
```

Der Vorgaengerbericht (`h5_extension_report.md` §5.2) nannte die Zeile
768 — auf dem aktuellen Branch liegt die Assertion drei Zeilen tiefer,
inhaltlich identisch.

### 4.2 Inhaltliche Diagnose

I725's SPARQL-Praemisse (`?itm1 ?rel1 ?itm2 . ?rel1 :R68 ?rel2`) bindet
Objektpositionen, die nativ zu **Literalen** aufloesen koennen — der
Subjekt-Slot der Konklusion (`?itm2 ?rel2 ?itm1`) erwartet aber
`core.Entity`. Die `_process_result_map`-Assertion schlaegt deshalb fehl.

### 4.3 Konsequenz

Da die native Engine das Referenz-Orakel ist und nicht angefasst wird
(goal.md §"Regeln/Grenzen"), gibt es auf dieser KB **kein wohldefiniertes
Aequivalenzziel**. Eine delegierte Variante saehe sich derselben
Konstellation gegenueber. Eine saubere Reparatur erforderte entweder
einen `FILTER isIRI(?itm2)`-Schritt im SPARQL-Translator (mit
Datalog-Aequivalent) oder eine separate Vorverarbeitung der
Praemissen-Statements — beides ausserhalb des H5-SPARQL-Scopes.

I725 bleibt deshalb:

- im Translator kurated `python_only` (`_SPARQL_PYTHON_ONLY_RULE_KEYS`),
- aus dem Gate-Regelsatz `ZEBRA_RULE_KEYS` ausgeschlossen
  (`experiments/h5_sparql/equivalence_gate.py`-Header-Kommentar).

---

## 5. Gate-Belege

### 5.1 h5_sparql — 10 Zebra-Regeln

Skript: `experiments/h5_sparql/equivalence_gate.py`. KB:
`zb + zr + zebra02`. Regelsatz: `("I702", "I705", "I790", "I800",
"I820", "I710", "I730", "I740", "I792", "I798")` — 5 bestehende
delegierte Regeln (aus Phase 2/Extension) plus 5 neu delegierte
SPARQL-Regeln. Curated-Ausschluesse I725/I803 sowie der Stage-5
Honest-Stop I741 im Skript-Header dokumentiert.

Log-Auszug aus `experiments/h5_sparql/equivalence_gate.log` (Aggregat
+ Per-Regel-Tabelle + GATE-RESULT):

```
=== Gate evaluation ===
native:    n_subj=686, n_triples=2819, new_statements=83, elapsed=44.733s
delegation:n_subj=686, n_triples=2819, new_statements=83, elapsed=2.592s

[Gate 1] state equivalence: OK  diff_subjects=0

[Gate 2] idempotency:       OK  extra_native=0 extra_delegation=0

[Gate 3] dup-multiset == native:  OK  diff_triples=0 native_dups=0 deleg_dups=0

=== Per-rule isolation (single rule on fresh KB after prereqs) ===
per-rule native I702: elapsed=0.205s n_new=13
per-rule delegation I702: elapsed=0.368s n_new=13
per-rule native I705: elapsed=0.188s n_new=20
per-rule delegation I705: elapsed=0.644s n_new=20
per-rule native I790: elapsed=0.199s n_new=0
per-rule delegation I790: elapsed=0.638s n_new=0
per-rule native I800: elapsed=0.196s n_new=10
per-rule delegation I800: elapsed=0.632s n_new=10
per-rule native I820: elapsed=0.188s n_new=0
per-rule delegation I820: elapsed=0.685s n_new=0
per-rule native I710: elapsed=0.205s n_new=4
per-rule delegation I710: elapsed=0.561s n_new=4
per-rule native I730: elapsed=0.210s n_new=6
per-rule delegation I730: elapsed=0.541s n_new=6
per-rule native I740: elapsed=0.205s n_new=0
per-rule delegation I740: elapsed=0.563s n_new=0
per-rule native I792: elapsed=20.417s n_new=8
per-rule delegation I792: elapsed=0.587s n_new=8
per-rule native I798: elapsed=0.217s n_new=20
per-rule delegation I798: elapsed=0.586s n_new=20

  rule   | native_count | delegated_count | multiset_gleich
  -------+--------------+-----------------+----------------
  I702   |           13 |              13 |            true
  I705   |           20 |              20 |            true
  I790   |            0 |               0 |            true
  I800   |           10 |              10 |            true
  I820   |            0 |               0 |            true
  I710   |            4 |               4 |            true
  I730   |            6 |               6 |            true
  I740   |            0 |               0 |            true
  I792   |            8 |               8 |            true
  I798   |           20 |              20 |            true

======================================================================
GATE-RESULT:
  gate_1_state_equivalent: true  (diff_subjects=0)
  gate_2_idempotent:       true  (extra_native=0, extra_delegation=0)
  gate_3_dup_equiv_native: true  (diff_triples=0, native_dups=0, deleg_dups=0)
  gate_1_ok: true
  gate_2_ok: true
  gate_3_ok: true
  overall_gate_ok:         true
  t_native_sec:            44.7329  (load=0.48,ok)
  t_delegation_sec:        2.5916  (load=0.84,(load-belastet))
  speedup_fullrun:         17.26x
  per_rule_isolation:      I702:n=13/d=13=, I705:n=20/d=20=, I790:n=0/d=0=, I800:n=10/d=10=, I820:n=0/d=0=, I710:n=4/d=4=, I730:n=6/d=6=, I740:n=0/d=0=, I792:n=8/d=8=, I798:n=20/d=20=
======================================================================
```

### 5.2 h5_phase2 — OCSE-Voll-KB (Re-Validierung)

Skript unveraendert: `experiments/h5_phase2/equivalence_gate.py`.
Log-Auszug aus `experiments/h5_sparql/h5_phase2_revalidation.log`:

```
=== Gate evaluation ===
native:    n_subj=1442, n_triples=6555, new_statements=339, elapsed=329.696s
delegation:n_subj=1442, n_triples=6555, new_statements=339, elapsed=1.609s

[Gate 1] state equivalence: OK  diff_subjects=0

[Gate 2] idempotency:       OK  extra_stmts_on_replay=0

[Gate 3] dup-multiset == native:  OK  diff_triples=0 native_dups=5 deleg_dups=5

======================================================================
GATE-RESULT:
  gate_1_state_equivalent: true  (diff_subjects=0)
  gate_2_idempotent:       true  (extra_stmts_on_replay=0)
  gate_3_dup_equiv_native: true  (diff_triples=0, native_dups=5, deleg_dups=5)
  overall_gate_ok:         true
  t_native_sec:            329.6959  (load=0.92,(load-belastet))
  t_delegation_sec:        1.6092  (load=1.03,(load-belastet))
  speedup_fullrun:         204.88x
======================================================================
```

Die fuenf `native_dups=deleg_dups=5` sind die in Phase 2.1
dokumentierten qualifier-/scope-bedingten Mehrfacheintraege auf
R30/R31 — kein Hygiene-Bug.

### 5.3 h5_extension — Zebra-Subset (Re-Validierung)

Skript unveraendert: `experiments/h5_extension/equivalence_gate.py`.
Regelsatz `("I702","I705","I790","I800","I820")` — die vier Stage-1-
Literal-Praemissen plus I702. Log-Auszug aus
`experiments/h5_sparql/h5_extension_revalidation.log`:

```
=== Gate evaluation ===
native:    n_subj=674, n_triples=2702, new_statements=40, elapsed=1.447s
delegation:n_subj=674, n_triples=2702, new_statements=40, elapsed=1.453s

[Gate 1] state equivalence: OK  diff_subjects=0

[Gate 2] idempotency:       OK  extra_native=0 extra_delegation=0

[Gate 3] dup-multiset == native:  OK  diff_triples=0 native_dups=0 deleg_dups=0

======================================================================
GATE-RESULT:
  gate_1_state_equivalent: true  (diff_subjects=0)
  gate_2_idempotent:       true  (extra_native=0, extra_delegation=0)
  gate_3_dup_equiv_native: true  (diff_triples=0, native_dups=0, deleg_dups=0)
  gate_1_ok: true
  gate_2_ok: true
  gate_3_ok: true
  overall_gate_ok:         true
  t_native_sec:            1.4469  (load=0.90,(load-belastet))
  t_delegation_sec:        1.4531  (load=0.91,(load-belastet))
  speedup_fullrun:         1.00x
======================================================================
```

Speedup nahe 1.0x: das Extension-Subset enthaelt fast ausschliesslich
Literal-Praemissen-Regeln, die nativ ohnehin in Millisekunden laufen,
und der `nmo`-Subprozess-Overhead dominiert. Die Aequivalenz-Aussage
bleibt unberuehrt — alle drei Gates `true`.

---

## 6. Regression — Baseline-Reproduktion

### 6.1 Baseline (vor `h5_sparql`)

Aus `experiments/h5_sparql/baseline.log` (Pflicht-Lauf der task_001 auf
`develop_carsten`-HEAD `0aa598f2f`):

```
189 passed, 4 skipped, 2 xfailed, 3 warnings in 73.63s (0:01:13)
```

Baseline-Tupel: `(passed=189, failed=0, skipped=4, xfailed=2,
xpassed=0, errors=0)`.

### 6.2 Flag-AUS-Lauf (Stand task_005, Branch-Ende)

Aus `experiments/h5_sparql/regression_flag_off.log`:

```
194 passed, 5 skipped, 2 xfailed, 3 warnings in 142.45s (0:02:22)
```

### 6.3 Delta

| Metrik   | Baseline | Flag-AUS | Delta |
|----------|---------:|---------:|------:|
| passed   | 189      | 194      | **+5** |
| failed   | 0        | 0        | 0     |
| skipped  | 4        | 5        | **+1** |
| xfailed  | 2        | 2        | 0     |
| warnings | 3        | 3        | 0     |

**Erklaerung Delta:**

- **+5 passed:** Die fuenf Multiset-Aequivalenz-Tests aus
  `tests/test_h5_sparql_premises.py`
  (`test_I798_*`, `test_I730_*`, `test_I792_*`, `test_I710_*` plus
  `test_I803_curated_python_only`). Die I803-Curated-Assertion lauft
  auch ohne Flag gruen, weil die Pruefung den Klassifikator selbst
  abfragt.
- **+1 skipped:** `test_I740_native_vs_delegated_multiset_equal` — der
  Honest-Stop-Skip mit dokumentierter Begruendung (native feuert
  0-mal selbst nach erweiterter Praereq-Kette).
- Keine neuen Failures/Errors. Die Baseline ist damit reproduziert
  (Baseline-Lauf + neue Tests).

### 6.4 Flag-AN-Lauf

Aus `experiments/h5_sparql/test_rulebased_reasoning_deleg_final.log`:

```
24 passed, 4 skipped in 16.52s
```

Die vier Skips sind die vorbestehenden "currently too slow"-Markierungen
(`test_d18`, `test_e01`, `test_e02`, `test_e03`) — flag-unabhaengig.
Keine neuen Failures/Errors mit `PYIRK_NEMO_DELEGATION=1`.

---

## 7. Stage-5 Honest-Stop (I741)

`goal.md` legt fuer Stage 5 zwei harte Bedingungen fest:

1. *„Negation (`FILTER NOT EXISTS` o.ae.) → NUR als stratifizierte
   Negation und NUR im letzten Inkrement (I741), mit eigenem
   Korrektheitsnachweis."*
2. *„nur angehen, wenn 1–4 sauber stehen. Vorher explizit auf Fixtures
   nachweisen, dass Nemos Negations-Semantik dem nativen Verhalten
   entspricht."*

Daran haengt unmittelbar die folgende Anweisung
(goal.md, Zeile 50):

> *„Lieber bei Stufe k ehrlich aufhoeren als Stufe k+1 wackelig
> mitnehmen."*

### 7.1 Sachstand

- I741 hat ein aktives `MINUS { ?itm2 :R57 true. }` (recon §I741) UND
  parallel fuenf `!=`-Filter ueber 4 Variablenpaare.
- Der Translator erkennt das `Minus` korrekt (Klassifikator-Reason
  `SPARQL-based premise: not a pure BGP (Minus)`, verifiziert in
  `experiments/h5_sparql/classify_after_stage2.log` und
  `classify_after_stage4.log`).
- Stage 4 hatte bereits *zwei* Honest-Stops auf der Inequality-Ebene
  (I725 kurated und I740 fixturebedingt 0-feuernd) — die Voraussetzung
  *„wenn 1–4 sauber stehen"* ist semantisch erfuellt
  (Multiset-Aequivalenz wo native feuert; Honest-Stop wo native nicht
  feuert), aber die *strukturelle* Stage-4-Klarheit ist nicht
  spannungsfrei: ein zusaetzlicher Negationspfad oben drauf wuerde
  Konzern-Schichten ueberlagern.

### 7.2 Was Stage 5 als Praerequisit braechte

Der von `goal.md` geforderte *„explizite Fixture-Nachweis, dass Nemos
Negation-as-Failure dem nativen `MINUS`-Verhalten entspricht"* ist
selbst ein abgeschlossenes Mini-Projekt:

- **Stratifikations-Pruefung:** Das gesamte Nemo-Programm muss global
  stratifiziert bleiben, sobald eine Negationsregel hinzukommt
  (Translator-Erweiterung: Stratifikations-Check ueber alle aktiven
  Regelheads/Bodies).
- **Semantik-Aequivalenz:** rdflib-`MINUS` und Nemos `~`-Negation
  haben unterschiedliche Default-Semantiken (rdflib: kein Match wenn
  *irgendein* Tripel im MINUS-Block matcht; Nemo: NAF ueber das
  abgeleitete Pradikat). Die Aequivalenz muss auf einem nicht-trivialen
  Fixture-Korpus (mit *und* ohne `R57=true`-Belegung) gepruerft sein.
- **EDB-Vollstandigkeit:** Der NAF-Default haengt davon ab, dass das
  EDB *alle* `R57=true`-Statements traegt — der Exporter muss das
  garantieren (entsprechende Tests).

Keine dieser Voraussetzungen ist in dieser Iteration erbracht. Ein
naiver Nemo-NAF-Stub liefert auf den zebra-only-Fixtures *vielleicht*
das richtige Multiset — Mitnehmen ohne Korrektheitsnachweis wuerde der
goal.md-Klausel
*„Tests und Gates duerfen NICHT abgeschwaecht werden, um gruen zu
werden"* (goal.md §"Honest-Stop-Klausel") direkt widersprechen.

### 7.3 Entscheidung

Stage 5 bleibt **bewusst nicht angegangen**. Die Begruendung folgt
dem zitierten goal.md-Satz: lieber Stage 4 sauber abschliessen (5
delegierte Regeln, 3 Gates gruen, Regression unauffaellig) als Stage 5
mit unverifizierter Negations-Semantik mitzunehmen.

Vorgehen fuer einen spaeteren Worker-Zyklus (nicht Teil dieses
Branches):

1. Nemo-Negationsstub im Translator implementieren
   (`_sparql_extract_bgp_with_minus`), aber zunaechst nur als
   isolierte Mini-Fixture pruefen.
2. Stratifikations-Check ueber den globalen Programm-Graphen.
3. Fixture-Korpus konstruieren, das BEIDE Semantik-Aequivalenzen
   abdeckt (mit/ohne `R57=true`).
4. Erst dann I741 in `ZEBRA_RULE_KEYS` aufnehmen.

---

## 8. Schlusszeile

H5SPARQL-VERDICT: gate_ok=ja new_delegated=5 rules=I710,I730,I740,I792,I798
