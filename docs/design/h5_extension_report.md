# H5 Extension — Abschlussbericht: Erweiterung des delegierbaren Regelsatzes

> Branch: `h5_extension` (HEAD = `14f784b1`) · Stand: 2026-06-12

---

## 1. Zusammenfassung

Phase 1 dieser Iteration liefert **vier neue delegierbare Regeln** in der
Kategorie *Literal-Praemissen*: **I705, I790, I800, I820**. Diese Regeln
laufen jetzt mit aktivem `PYIRK_NEMO_DELEGATION=1` ueber den Nemo-Pfad und
sind in Multiset-Aequivalenz zum nativen Lauf belegt. Die in `goal.md`
priorisierten Folge-Kategorien bleiben in dieser Iteration `python_only`
mit dokumentierten *Honest-Stops*: I702 wegen Konsequent-Callback in der
Konklusion; I720 wegen `cm.new_condition_func`-Callbacks in beiden
OR-AND-Branches (laut `goal.md` explizit out of scope); die acht
SPARQL-Praemissen-Regeln (I710, I725, I730, I740, I741, I792, I798, I803)
ohne saubere Translator-Erweiterung. Beide Akzeptanz-Gates sind gruen:
das neue Zebra-Subset-Gate (`experiments/h5_extension/equivalence_gate.py`)
und das uebernommene OCSE-Phase-2-Gate liefern jeweils
`overall_gate_ok=true`.

---

## 2. Phase 1 — Literal-Praemissen (geliefert)

### 2.1 Uebersicht

| Regel | Literal-Konstellation in der Praemisse | Status | Mini-Fixture-Test |
|---|---|---|---|
| I705 | zwei `R57=False`-Statements (`bool`) | `direct` | `tests/test_h5_extension_literal_premises.py::test_I705_*` |
| I790 | ein `R38=1`-Statement (`int`) | `direct` | `tests/test_h5_extension_literal_premises.py::test_I790_*` |
| I800 | ein `R2850=True`-Statement (`bool`) | `direct` | `tests/test_h5_extension_literal_premises.py::test_I800_*` |
| I820 | sechs `R57=True/False`-Statements (`bool`) plus Joins ueber `R50`/`R4` | `direct` | `tests/test_h5_extension_literal_premises.py::test_I820_*` |

### 2.2 Regel-Charakterisierung

**I705 — *deduce trivial different-from-facts*** (`tests/test_data/zebra_puzzle_rules.py:61-83`).
Vier Tripel-Praemissen: zwei `R4__is_instance_of zb.I7435["human"]`, dazu zwei
`R57__is_placeholder=False`. Konklusion ist ein reines Tripel
`(p1, R50__is_different_from, p2)` mit Qualifier `ptg_mode=5`. In der
nativen Engine ist `ptg_mode=5` lediglich der `omit_if_existing`-Marker
(`ruleengine.py:977`), der vom Delegationspfad bereits durch die V3-
Pruefung in `_materialize_tuples` (Phase 2) gespiegelt wird; eine
Qualifier-Materialisierung auf das neue Statement ist deshalb nicht
notwendig (siehe `task_002_result.md`).

**I790 — *infer from 'is one of' → 'is same as'*** (`zebra_puzzle_rules.py:505-522`).
Drei Tripel-Praemissen: `(itm1, R56, tup1)`, `(tup1, R38, 1)`,
`(tup1, R39, elt0)`. Das R38-Literal `1` (`int`) ist die einzige
Konstante; die Konklusion ist ein reines Tripel `(elt0, R47, itm1)`.
Sauberster „goldener Fall" der Phase, weil das Literal als Ground-Term-
Konstante in der Praemisse steht.

**I800 — *mark relations which are opposite of functional activities***
(`zebra_puzzle_rules.py:744-765`). Praemisse `(rel1_not, R43, rel1)` plus
`(rel1, zb.R2850, True)`. Konklusion enthaelt selbst Literal-Objekte
(`(rel1_not, R6020, True)` und `(rel1_not, R71, True)`); im
`fact`-Schema sind das LIT:-Token in den Tupel-Spalten — ein einziger
Pfad fuer Praemisse und Konklusion.

**I820 — *deduce personhood by exclusion*** (`zebra_puzzle_rules.py:857-916`).
Die strukturell groesste Regel der Kategorie: sechs Var-Quantoren ueber
Humans (jeweils `R4=zb.I7435`), ein `R57=True` plus fuenf `R57=False`,
zusaetzlich mehrere `R50__is_different_from`-Ketten. Trotz der Groesse
formell ein reines BGP mit Literal-Konstanten, das `direct` matched, sobald
Literale exportiert werden — die `?x != ?y`-Inequality-Spiegelung der
nativen Subgraph-Monomorphie geschieht im neuen `_build_direct_snippet`
(siehe 2.3, Spiegelung).

### 2.3 Exporter-Erweiterung — `literal_triples.csv`

`src/pyirk/nemobridge/exporter.py` schreibt seit dieser Phase eine
zusaetzliche Datei `literal_triples.csv` mit Spalten
`(subj_uri, pred_uri, LIT:<repr>)`. Der `LIT:`-Praefix
(`exporter.py:59`) trennt Literal-Tokens trennscharf von URI-Tokens; die
Rueck-Dekodierung in `delegation._decode_object_cell` nutzt
`ast.literal_eval` (vgl. `task_002_result.md`).

Der Typfilter `_NEMO_SAFE_LITERAL_TYPES = (bool, int, float)`
(`exporter.py:70`) laesst String-Literale bewusst aus: Nemo 0.10
verdoppelt jeden Backslash beim Schreiben string-getypter Output-Zellen,
weshalb Strings im Round-Trip nicht verlustfrei rueckdekodierbar waeren.
Die fuer H5-Phase 1 relevanten Zebra-Regeln (I705/I790/I800/I820) benoetigen
ausschliesslich bool/int — die Einschraenkung kostet hier nichts. Die
Datei wird auch dann geschrieben, wenn sie leer ist, damit der
`@import literal_triples` im generierten `.rls` nicht aufgrund einer
fehlenden Datei abbricht.

Die Translator-Seite zieht im `fact`-Modell ein zusaetzliches
Seed-Statement nach: `fact(?s, ?p, ?o) :- literal_triples(?s, ?p, ?o) .`
(vgl. `translator.py`, Header). Praemissen mit Literal-Objekt landen
damit ueber denselben `fact`-Knoten wie URI-Tripel.

### 2.4 Klassifikations-Snapshot (Zebra-Regeln)

| Lauf | direct | transitive | python_only |
|---|---|---|---|
| Vor Phase 1 | 4 | 1 | 24 |
| Nach Phase 1 | 8 | 1 | 20 |

Delta: vier Regeln wandern `python_only` → `direct` (I705, I790, I800,
I820). Die `direct`-Liste umfasst danach: I64, I65, I763, I796 (vorher
delegierbar) plus die vier neuen.

Latenter Bug, gemeinsam mit Phase 1 behoben (siehe `task_002_result.md`):
`_var_name` emittierte fuer *externe* Entities (z. B. `zb.I7435["human"]`
in I763/I796) bislang unbeschraenkte Datalog-Variablen wie `?I7435`.
`_obj_term` unterscheidet jetzt sauber Literal → `"LIT:<repr>"`,
Scope-Internal-Variable → `?name`, externes Entity → `"<uri>"`. Das
Phase-2-OCSE-Gate hat den Bug nicht erwischt, weil OCSE I763/I796 nicht
beruehrt; die Phase-2-Re-Validierung in dieser Iteration (siehe 6.2)
bestaetigt, dass die Korrektur die OCSE-Aequivalenz nicht stoert.

---

## 3. Honest-Stop: I702

I702 (`rule: add reverse statement for symmetrical relations`,
`zebra_puzzle_rules.py:43-56`) bleibt `python_only`. Die Praemisse selbst
besteht zwar nur aus einem Literal-Statement (`rel1 R42 True`), das durch
den Phase-1-Literal-Export grundsaetzlich abbildbar waere. Blockiert wird
die Delegation an der **Konklusion**: I702 ruft `cm.consequent_func(
reverse_statements, …)` auf, was im Assertion-Scope ein
Anchor-Item (`fiat_factory_item0`) erzeugt. Der Klassifikator erkennt
das in Stufe 8 (`assert_items` nicht leer) und liefert genau die
Begruendung `"Assertion creates new entities (fiat prototypes):
['fiat_factory_item0']"`.

Inhaltlich beschreibt I702 ein Schema-Statement (R42 markiert eine
Relation als symmetrisch) und leitet daraus pro existenter
`(?s, rel1, ?o)`-Faktenzeile ein gespiegeltes `(?o, rel1, ?s)` ab. Das
liesse sich in Datalog formulieren — aber die Konklusion bezieht sich
nicht auf Praemissen-Variablen, sondern auf einen *anderen* Faktenraum,
und die `direct`-Snippet-Form bildet das nicht ab. Eine korrekte
Delegation wuerde eine eigene Translator-Erweiterung verlangen
(„R42-Marker-getriebener Dual-Stream"). Auf den Zebra-Daten ist R42 nur
auf `R3606["lives next to"]` gesetzt; der inkrementelle Gewinn waere
gering. Bewusst nicht angegangen, weil ein sauberes Inkrement die
Form-Annahme des Translators sprengen wuerde.

---

## 4. Honest-Stop: I720 (OR-Subscope)

I720 (`rule: replace (some) same_as-items`,
`zebra_puzzle_rules.py:133-171`) ist die einzige Zebra-Regel in der
OR-Subscope-Kategorie. Klassifikator-Reason heute:
`"OR-subscope in premise — branching not translatable to Datalog"`.

Recon §E.2 dokumentiert die OR-Struktur: drei AND-Branches, davon zwei
explizit ueber `with cm_OR.AND() as cm_AND` und ein direkter
`cm_OR.new_rel`. Eine reine Disjunktions-Erweiterung des Translators
(mehrere Datalog-Regeln mit gleichem Head, eine pro AND-Branch) waere
prinzipiell denkbar, scheitert hier jedoch an einer harten Schranke: die
ersten beiden AND-Branches enthalten **`cm.new_condition_func`-Callbacks**
(`label_compare_method`, `does_not_have_relation`). Damit waere I720 selbst
bei perfekter OR-Uebersetzung weiterhin durch Condition-Callbacks
blockiert — und Condition-Callbacks sind in `goal.md` ausdruecklich out
of scope (Bucket „Condition-Callbacks", I750/I794). I720 bleibt deshalb
`python_only` mit dokumentierter Doppel-Blockade.

---

## 5. Honest-Stop: SPARQL-Praemissen (8 Regeln)

### 5.1 Inventar (aus Recon §E.3)

| Regel | Muster | Hinweise |
|---|---|---|
| I710 | reines BGP + Literal-Konstante + `FILTER (?p1 != ?p2)` | Inequality, Nemo `!=`-Built-in noetig |
| I725 | reines BGP (2 Tripel, keine Filter) | sauberster Inverse-Pattern (`R68`-Vermittlung) |
| I730 | reines BGP, 4 Tripel + Literal-Konstante | Phase-1-naher Fall |
| I740 | reines BGP, 6 Tripel + 5× FILTER `!=` + 1 Literal | viele Inequalities |
| I741 | BGP + stratifizierte Negation (`MINUS { ?itm2 :R57 true.}`), 8 Tripel | aktives MINUS |
| I792 | reines BGP, 7 Tripel + 3 Literal-Konstanten | strukturell delegierbar |
| I798 | reines BGP, 4 Tripel + Literal-Konstante | strukturell der einfachste Fall |
| I803 | reines BGP, 7 Tripel + 2 Literal-Konstanten + Inequality | Tupel-Membership-Kette |

Strukturell ist keine dieser Regeln „nicht uebersetzbar". Reine BGPs
bilden 1:1 auf das `fact`-Schema ab; FILTER `!=` ist mit der bereits in
`_build_direct_snippet` verwendeten Inequality-Konvention ausdrueckbar;
stratifizierte Negation laesst sich in Nemo 0.10 als Negation-as-Failure
modellieren, wenn das Programm global stratifiziert ist.

### 5.2 Konkreter Diagnose-Befund (task_004)

Bei der Vorbereitung des Zebra-Gates trat eine Stop-Bedingung in der
nativen Engine selbst auf: `apply_semantic_rules` mit allen Zebra-Regeln
auf der minimalen `zb+zr`-KB faellt in I725 mit
`AssertionError: assert isinstance(new_subj, core.Entity)`
(`ruleengine.py:768`). I725 ist die einfachste SPARQL-Inverse-Regel und
hat eine vollkommen freie Praemisse `?itm1 ?rel1 ?itm2.
?rel1 :R68 ?rel2.`. Auf der reduzierten Datenbasis bindet diese Praemisse
Objektpositionen, die zu Literalen aufloesen — und der Subjekt-Slot der
Konklusion erwartet eine `core.Entity`. Reproduziert isoliert in
`/tmp/h5ext_diag/native_repro6.py` (vgl. `task_004_result.md`).

Damit faellt die *native* I725 schon ohne Delegation. Eine delegierte
Variante saehe sich derselben Konstellation gegenueber — das BGP wuerde
Literal-Bindungen produzieren, die der Materialisierungspfad in
`_materialize_tuples` ebenfalls als Subjekt nicht akzeptieren koennte.
Korrektur erfordert entweder eine Filter-Schicht im SPARQL-Translator
(`FILTER isIRI(?itm2)` mit Datalog-Aequivalent) oder eine separate
Vorverarbeitung der Praemissen-Statements. Beides ist machbar, aber
nicht Phase-1-Material.

### 5.3 Honest-Stop dieser Kategorie

In dieser Iteration wurde **keine SPARQL-Regel uebersetzt**. Rationale:
ein sauberes Inkrement (SPARQL-Translator-Erweiterung um BGP/Filter/
Negation, plus Mini-Fixture pro Regel, plus Gate-Verifikation) erfordert
mehrere Worker-Iterationen, die im verbleibenden Budget nicht risikoarm
leistbar waren. Ein wackeliges SPARQL-Subset („I725 ohne Literal-Filter")
auszuliefern wuerde gegen die Honest-Stop-Klausel aus `goal.md`
verstossen. Die Regel-Inventar-Aufschluesselung in 5.1 ist als Vorlage
fuer einen spaeteren Worker-Zyklus formuliert (I798 als kleinster Einstieg,
dann I725 mit Literal-Filter, danach BGP+Inequality-Familie).

---

## 6. Akzeptanz-Gate — Belege

### 6.1 Zebra-Gate (kuratiertes Subset)

Skript: `experiments/h5_extension/equivalence_gate.py`. Das Skript wendet
explizit das Tupel `RULE_KEYS = ("I702","I705","I790","I800","I820")`
an — die vier neu delegierten Regeln plus I702 als bereits in der
Test-Suite genutzten Stabilisator. Hintergrund der Subset-Wahl: ein
naiver `apply_semantic_rules(*get_all_rules(), exhaust=True)`-Lauf
faellt in der nativen Engine wegen I725 (siehe 5.2). Das Subset entkoppelt
das Aequivalenz-Argument fuer die delegierten Regeln von der
unabhaengigen I725-Diagnose (vgl. `task_004_result.md`).

Log-Auszug aus `experiments/h5_extension/equivalence_gate.log`:

```
=== Pfad A — native (subprocess) ===
subprocess native done: elapsed=1.838s n_new_first=40 n_subj=674 n_triples=2702 idem_n_new=0
native subprocess wall: 5.901s

=== Pfad B — delegation (subprocess) ===
subprocess delegation done: elapsed=1.259s n_new_first=40 n_subj=674 n_triples=2702 idem_n_new=0
delegation subprocess wall: 4.955s

=== Gate evaluation ===
native:    n_subj=674, n_triples=2702, new_statements=40, elapsed=1.838s
delegation:n_subj=674, n_triples=2702, new_statements=40, elapsed=1.259s

[Gate 1] state equivalence: OK  diff_subjects=0
[Gate 2] idempotency:       OK  extra_native=0 extra_delegation=0
[Gate 3] dup-multiset == native:  OK  diff_triples=0 native_dups=0 deleg_dups=0

GATE-RESULT:
  gate_1_state_equivalent: true  (diff_subjects=0)
  gate_2_idempotent:       true  (extra_native=0, extra_delegation=0)
  gate_3_dup_equiv_native: true  (diff_triples=0, native_dups=0, deleg_dups=0)
  overall_gate_ok:         true
  t_native_sec:            1.8384  (load=2.36,(load-belastet))
  t_delegation_sec:        1.2592  (load=2.53,(load-belastet))
  speedup_fullrun:         1.46x
```

Speedup `1.46x`: das Subset enthaelt fast ausschliesslich
Literal-Praemissen-Regeln, die in der nativen Engine ohnehin in
Millisekunden laufen. Der Subprocess-Overhead von Nemos `nmo`-Aufruf
dominiert das Mess-Ergebnis. Der Speedup-Wert ist Ausdruck der
Subset-Wahl, nicht der Phase-1-Implementierung — alle drei Gates sind
gruen, die Aequivalenz ist die eigentliche Aussage.

### 6.2 OCSE-Phase-2-Gate (Re-Validierung)

Skript unveraendert: `experiments/h5_phase2/equivalence_gate.py`.
Log-Auszug aus `experiments/h5_extension/ocse_revalidation.log`:

```
[Gate 1] state equivalence: OK  diff_subjects=0
[Gate 2] idempotency:       OK  extra_stmts_on_replay=0
[Gate 3] dup-multiset == native:  OK  diff_triples=0 native_dups=5 deleg_dups=5

GATE-RESULT:
  gate_1_state_equivalent: true  (diff_subjects=0)
  gate_2_idempotent:       true  (extra_stmts_on_replay=0)
  gate_3_dup_equiv_native: true  (diff_triples=0, native_dups=5, deleg_dups=5)
  overall_gate_ok:         true
  t_native_sec:            351.8417  (load=2.02,(load-belastet))
  t_delegation_sec:        1.6535  (load=3.05,(load-belastet))
  speedup_fullrun:         212.78x
```

`overall_gate_ok=true` — die Phase-1-Aenderungen an Exporter/Translator
(Literal-Export, `_obj_term`-Typunterscheidung, Inequality-Constraints in
`_build_direct_snippet`, `restrict_to`-Filter) stoeren die in Phase 2.1
hergestellte OCSE-Aequivalenz nicht. Die fuenf nativen R30/R31-Duplikate
sind unveraendert (siehe Phase-2-Bericht §7.4 — kein Hygiene-Bug,
sondern qualifier-/scope-bedingte Mehrfacheintraege).

### 6.3 Regression-Sanity

| Suite | Flag | Ergebnis |
|---|---|---|
| `tests/test_rulebased_reasoning.py` | AUS | 24 passed, 4 skipped |
| `tests/test_rulebased_reasoning.py` | `PYIRK_NEMO_DELEGATION=1` | 24 passed, 4 skipped |
| `tests/test_h5_extension_literal_premises.py` | (Subprozess setzt Flag) | 4 passed |

Die 4 Skips in `test_rulebased_reasoning.py` sind die vorbestehenden
„currently too slow"-Markierungen (`test_d18`, `test_e01`, `test_e02`,
`test_e03`); kein neuer Skip durch H5-Extension. Volle Suite
(`pytest -p no:randomly --ignore=tests/test_script.py`) lief auf
**172 passed, 4 skipped, 2 xfailed** — identisch mit und ohne Flag.
`tests/test_script.py` ist mit drei Failures + einem Error wegen
fehlendem `pyirk`-CLI im Container-PATH vorbestehend und nicht durch
H5-Extension verursacht (vgl. `task_002_result.md`).

---

## 7. Performance-Beobachtung (informativ)

Die Zahlen sind als Beobachtung markiert, nicht als Benchmark — VPS-Last
schwankt, Nemo-`nmo`-Startoverhead ist nicht in den Phase-1-Code
gerechnet. Maerker `(load-belastet)` ist self-induced durch den
parallelen Mess-Subprozess.

| Gate | t native | t delegation | Speedup | Kommentar |
|---|---|---|---|---|
| Zebra-Extension-Gate | 1.838 s | 1.259 s | 1.46x | Subset zu klein, Subprocess-Overhead dominiert |
| OCSE-Phase-2-Gate | 351.84 s | 1.65 s | 212.78x | graph-premise-Regeln; Hauptwert von H5 |

Phase-2-Bericht (`docs/design/h5_phase2_report.md` §7.4) berichtet auf
weniger belastetem System `376.01x` fuer denselben OCSE-Gate-Lauf.
Die `212x`-Zahl hier liegt unter dieser Marke, weil der Lauf bei
`load=2.02–3.05` (self-induced) gemessen wurde. Die Groessenordnung
„mehrere Hundert ×" bleibt stabil; das ist die belastbare Aussage.

---

## 8. Was als naechstes

**I720 (OR-Subscope)** ist nur dann delegierbar, wenn der
Condition-Callback-Block separat geknackt wird. Eine
Translator-Erweiterung fuer reine OR-Disjunktion (mehrere
Head-gleiche Datalog-Regeln) loest I720 allein nicht — `goal.md` haelt
Callback-Anker ausdruecklich out of scope, deshalb ist hier eine
Interface-Entscheidung noetig, bevor ein Worker-Zyklus sinnvoll
investiert.

**SPARQL-Translator (BGP-Subset)** ist machbar und sollte in einem
eigenen Worker-Zyklus mit (a) Translator-Erweiterung um BGP →
`fact`-Konjunktion, (b) FILTER `!=` als Inequality-Constraint, (c)
pro-Regel-Fixture-Test, (d) Re-Lauf des Zebra-Gates ueber ein
gewachsenes `RULE_KEYS`-Tupel angegangen werden. Reihenfolge-Vorschlag:
I798 (kleinstes BGP) → I730/I792 (BGP + Literal) → I725 (mit
Literal-Filter, gleichzeitig native-Engine-Verhalten klaeren) → I710/
I740/I803 (BGP + Inequality) → I741 (stratifizierte Negation, eigenes
Pruef-Inkrement).

**Phase-2.1-Kalibrierung (Dup-Multiset gegen nativ)** bleibt der
Goldstandard fuer weitere Gates: jede zusaetzliche oder fehlende
Dublette gegenueber nativ faellt durch, native-eigene Mehrfacheintraege
werden der Delegation nicht angelastet. Spaetere Phasen sollten
dieses Kriterium beibehalten und nicht durch absolute
Duplikat-Schwellen ersetzen.

---

H5EXT-VERDICT: gate_ok=ja new_delegated=4 categories=literal_premises
