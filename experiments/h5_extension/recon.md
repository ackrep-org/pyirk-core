# H5-Extension — Reconnaissance-Memo (Phase-0)

> Branch: `h5_extension` · Stand: 2026-06-12
> Vorbedingung (aus task_001.md): Branch von `develop_carsten` abgezweigt,
> `git status` zu Beginn `nothing to commit`. Kein Code geändert; reine
> Lese-Recon.

Belegstellen sind `path:line` relativ zum Repo-Root. Code-Snippets sind 1:1
Auszüge — falls Inhalt unverändert klar bleibt, gekürzt mit `…`.

---

## A) Klassifikation

### A.1 Wo lebt `classify_rules`?

`src/pyirk/nemobridge/translator.py:249-260`:

```python
def classify_rules(ds) -> list:
    """…
    Categories:
      'direct'      — pure triple-pattern premise/assertion; rls_snippet filled.
      'transitive'  — I66-type with R60__is_transitive; covered by generate_transitivity_facts.
      'python_only' — requires Python callbacks, SPARQL, OR-scopes, or fiat items.
    """
    rules = _get_all_rules(ds)
    return [_classify_single_rule(rule) for rule in rules]
```

Re-Export über `src/pyirk/nemobridge/__init__.py` (Phase-1-Bericht §2, dort
zitiert). Verwendung im Delegations-Pfad: `src/pyirk/nemobridge/delegation.py:50-58`
über `_split_rules_by_nemo_delegation(rules)`.

### A.2 Welche Funktion entscheidet `python_only`?

Die einzelne Klassifikationslogik liegt in `_classify_single_rule(rule)`
(`src/pyirk/nemobridge/translator.py:119-204`). Der Pfad nach `python_only`
ist **8-stufig**, in genau dieser Reihenfolge:

| # | Bedingung | file:line |
|---|---|---|
| 1 | `_has_cheat(rule)` — `rule.cheat` ist gesetzt | `translator.py:137-138` |
| 2 | `_has_sparql_premise(rule)` — Prämisse hat `R63__has_SPARQL_source` | `translator.py:141-142` |
| 3 | `_has_or_subscope(rule)` — Prämisse hat `scp__OR` | `translator.py:145-146` |
| 4 | `prem_items` nicht leer — Condition-Callback-Anker-Items in der Prämisse | `translator.py:154-156` |
| 5 | `not prem_stms` — leere Prämisse | `translator.py:158-159` |
| 6 | `literal_stmts and not (r60_stmts and wildcard_stmts)` — Literal-Werte in der Prämisse, ohne dass es das R2-Muster ist | `translator.py:181-183` |
| 7 | `wildcard_stmts` ohne R60 — R58-Wildcard ohne Transitivitätsmuster | `translator.py:186-187` |
| 8 | `assert_items` nicht leer — Konklusion erzeugt neue Entities (fiat-Item-Prototypen) | `translator.py:195-197` |

Zusätzliche `python_only`-Pfade bei Fehlern:

- `_filter_stms(rule.scp__premise)` wirft → `python_only` mit `reason=Error extracting…` (`translator.py:152`).
- `_filter_stms(rule.scp__assertion)` wirft → analog (`translator.py:193`).
- `_build_direct_snippet` wirft → `python_only` mit `reason=RLS snippet generation failed:…` (`translator.py:203-204`).

Nur wenn alle 8 Bedingungen verneint sind, fällt eine Regel auf `direct`
(`translator.py:200-202`) bzw. bei Punkt-6-Spezialfall (R60-Marker + R58-Wildcard
zusammen) auf `transitive` (`translator.py:173-178`).

### A.3 Bucket-Trigger laut goal.md

| Bucket aus goal.md | Trigger-Funktion / Bedingung | file:line |
|---|---|---|
| **SPARQL-Prämisse** | `_has_sparql_premise(rule)` prüft `rule.scp__premise.get_relations("R63__has_SPARQL_source", return_obj=True)` | `translator.py:72-73` |
| **Literal-Werte** | Inspektion in `_classify_single_rule`: `if _is_literal(obj): literal_stmts.append(stm)` mit `_is_literal` = `isinstance(obj, p.allowed_literal_types)` | `translator.py:87-89` + `translator.py:166-167` |
| **fiat-Items (Konklusion)** | `assert_items` aus `_filter_stms(rule.scp__assertion)` ist nicht leer (Items im Assertion-Scope ohne reine Tripel) | `translator.py:191-197` |
| **Condition-Callbacks (Prämisse)** | `prem_items` aus `_filter_stms(rule.scp__premise)` ist nicht leer (Condition-Func-Anker im Premise-Scope) | `translator.py:149-156` |
| **Cheat** | `_has_cheat(rule)` ↔ `getattr(rule, "cheat", None)` truthy | `translator.py:83-85` + `translator.py:137-138` |
| **OR-Subscope** | `_has_or_subscope(rule)` ↔ `getattr(rule.scp__premise, "scp__OR", None)` truthy | `translator.py:76-81` + `translator.py:145-146` |

Nicht in der goal.md-Liste, aber faktisch auch `python_only`:
**leere Prämisse** (Punkt 5 oben), **Wildcard ohne R60** (Punkt 7).
Letzteres ist hier auffällig: ein R58-Wildcard in der Prämisse ohne den
R60-Marker reicht **nicht** für den `transitive`-Pfad — der bisherige
Translator deckt nur das I66-Idiom.

---

## B) Exporter

### B.1 Wo wird das Literal-Objekt aus `triples.csv` herausgefiltert?

`src/pyirk/nemobridge/exporter.py:249-250`:

```python
if not hasattr(o, "uri"):
    continue  # literal object — excluded from entity-triple export
```

Innerhalb von `export_datastore`, in der Hauptschleife über alle
Subject-Role-Statements (`_iter_subject_role_statements`). Identische Logik
auch in `export_relation_facts` (`exporter.py:169-170`, dort mit dem Kommentar
*„literal — skip for entity-only export"*).

Hinweis: ebenfalls gefiltert wird bei `not hasattr(s, "uri") or not
hasattr(pred, "uri")` (`exporter.py:247-248`) — defensiv, beide Endpunkte
müssen Entities sein.

### B.2 `fact`-Schema des Exporters

Aktuell schreibt der Exporter **kein** `fact`-File — das `fact/3`-Schema ist
Konvention des **Translators** (`generate_rls`, siehe D). Was der Exporter
schreibt:

`triples.csv` (`exporter.py:285-289`):

```python
# --- write triples.csv ---------------------------------------------------
triple_rows.sort()
triples_path = os.path.join(out_dir, "triples.csv")
with open(triples_path, "w", newline="") as f:
    csv.writer(f).writerows(triple_rows)
```

Spalten: `(subj_uri, pred_uri, obj_uri)` — jede Spalte ist die **volle URI** als
String, z. B. `irk:/builtins#R83`. Beispielzeile (aus dem Recon-Lauf
gegen die OCSE-Phase-1-Tests gut belegt, hier aus dem Translator-Headerkommentar
zitiert, `translator.py:23`):

```
"irk:/builtins#R3","irk:/ocse/0.2/math#I4122","irk:/builtins#I123"
```

(Konkrete Spaltentypen siehe `triples`-Anweisung in `translator.py:309`:
`format=(string,string,string)`.)

### B.3 Weitere Eingangsdateien (neben `triples.csv`)

Aus `export_datastore` (`exporter.py:186-336`), siehe Übersichtstabelle im
Modul-Docstring (`exporter.py:14-31`):

| Datei | Spalten | file:line |
|---|---|---|
| `stmts.csv` | `(stmt_id, subj_uri, pred_uri, obj_uri)` — qualifizierte Statements (Reifikation) | `exporter.py:291-295` |
| `quals_<rel_key>.csv` (mehrere) | `(stmt_id, value)` — `value` = URI bei Entities, `repr()` bei Literalen; Dateiname nutzt `short_key` (nicht URI) | `exporter.py:297-304` |
| `triples__<pred_key>.csv` (optional, `per_predicate=True`) | `(subj_uri, obj_uri)` | `exporter.py:306-314` |
| `uri_index.csv` | `(short_key, uri)` — Audit-Sidecar, nicht mehr Auflösungsweg | `exporter.py:316-319` |

Tatsächlich an Nemo gereicht wird in Phase 2.1 nur `triples.csv` (siehe
`delegation._apply_via_nemo`, `delegation.py:118-159` — `nmo` wird mit
`--import-dir tmp_dir` aufgerufen, der RLS-Quelltext importiert ausschließlich
`triples.csv`).

---

## C) Translator

### C.1 Eintrittspunkt für eine Regel

Single-Rule-Klassifikation: `_classify_single_rule(rule)`
(`src/pyirk/nemobridge/translator.py:119-204`).
Generieren des ternären `fact`-Snippets: `_build_direct_snippet(rule,
prem_stms, assert_stms_filtered)` (`translator.py:207-242`).

Eine Prämissen-Statement-Tripel-Übersetzung in Datalog-Atome (`translator.py:216-220`):

```python
for stm in prem_stms:
    subj, pred, obj = stm.relation_tuple
    s_var = _var_name(subj)
    o_var = _var_name(obj)
    body_parts.append(f'fact({s_var}, "{pred.uri}", {o_var})')
```

`_var_name` (`translator.py:92-100`) liefert `?<name>` aus `R23__has_name_in_scope`
oder `?<short_key>`. Eine Konklusionszeile (`translator.py:228-232`):

```python
for stm in assert_stms_filtered:
    subj, pred, obj = stm.relation_tuple
    s_var = _var_name(subj)
    o_var = _var_name(obj)
    head_lines.append(f'fact({s_var}, "{pred.uri}", {o_var}) :- {body} .')
```

Bsp. Resultat (aus `translator.py:23-28`):

```
fact(?s, "irk:/builtins#R83", ?o) :- fact(?s, "irk:/builtins#R3", ?o) .
```

### C.2 Wo bricht / markiert der Translator `python_only` bei Literal-Prämisse?

`src/pyirk/nemobridge/translator.py:162-183`:

```python
r60_stmts, wildcard_stmts, literal_stmts = [], [], []
for stm in prem_stms:
    subj, pred, obj = stm.relation_tuple
    if _is_literal(obj):
        literal_stmts.append(stm)
        if pred == p.R60 and obj is True:
            r60_stmts.append(stm)
    if pred == p.R58:
        wildcard_stmts.append(stm)

# 6) I66-type: R60 check + wildcard relation → transitive
if r60_stmts and wildcard_stmts:
    return result("transitive", None, …)

# 7) Other literals in premise → python_only
if literal_stmts:
    desc = [(s.relation_tuple[1].short_key, repr(s.relation_tuple[2])) for s in literal_stmts]
    return result("python_only", None, f"Literal value(s) in premise (not triple-pattern): {desc}")
```

Bedingung: jede Prämissen-Statement-Triple mit literalem Objekt landet in
`literal_stmts`; **wenn nicht gleichzeitig das R60+R58-Idiom** vorliegt, fällt
die Regel auf `python_only` mit Reason `"Literal value(s) in premise…"`
(`translator.py:181-183`).

### C.3 Hypothese: wo würde OR-Subscope erkannt?

Aktuell **früh ausgeschlossen** über `_has_or_subscope(rule)` in der 3.
Klassifikationsstufe (`translator.py:76-81` + `:145-146`):

```python
def _has_or_subscope(rule) -> bool:
    try:
        return bool(getattr(rule.scp__premise, "scp__OR", None))
    except Exception:
        return False
…
if _has_or_subscope(rule):
    return result("python_only", None, "OR-subscope in premise — branching not translatable to Datalog")
```

Hypothese für die H5-Extension: an genau dieser Stelle (`_classify_single_rule`
nach SPARQL-Check, vor `_filter_stms`) ist der natürliche Hook-Punkt. Statt
sofort `python_only` zurückzugeben, könnten die OR-AND-Sub-Scopes per
`scp__OR` traversiert werden — pro AND-Branch ein eigener `body`-Cluster, der
in mehrere Datalog-Regeln (eine Kopfzeile pro AND-Branch, gleiches Tupel) zerfällt
(Datalog deckt Disjunktion durch mehrere Regeln mit gleichem Head). Das DSL liefert
die OR-Struktur über `with cm.OR() as cm_OR` (Beispiel I720 unten in §E),
intern als verschachtelte Sub-Scopes mit `R20__has_defining_scope`-Verkettung.
Ein Translator-Erweiterungspunkt müsste:
1. OR-Branches aus `rule.scp__premise.scp__OR` extrahieren,
2. Pro AND-Branch `_filter_stms` analog aufrufen,
3. Für jede AND-Branch einen separaten `fact(…) :- body_branch_i .`-Head
   pro Konklusion erzeugen.

(Reine Hypothese — kein Code geändert, kein DSL-Detail durchverifiziert.)

---

## D) Nemo-0.10-Kodierung (Spike-/Phase-1-/Phase-2-Beleg)

### D.1 Datenterme als volle URI mit String-Format

Validierte Encoding-Entscheidung Phase 2.1 — `docs/design/performance.md:146-150`:

> volle URIs als **quoted-String-Datenterme**, ternäres `fact(?s,?p,?o)`-Modell
> (Prädikate sind Datenwerte, nie Nemo-Prädikatnamen), `format=(string,…)`
> auf jedem CSV-Import (sonst joinen Zellen nicht mit `.rls`-Konstanten)

Ausführlicher in `docs/design/h5_phase2_report.md:256-265`:

> `triples.csv` und `stmts.csv` fuehren pro Spalte die volle URI
> (`irk:/<mod>#<short_key>`) statt eines short_key-Pfads. … Umstellung auf
> ein ternaeres Datalog-Modell `fact(?s, ?p, ?o)`. Jeder `@import` deklariert
> `format=(string, ...)`, Praedikate sind String-Konstanten mit voller URI
> (z. B. `"irk:/builtins#R83"`), ein einziger
> `@export fact :- csv{resource="output_fact.csv"} .` ersetzt die bisherigen
> `output_<REL>.csv`-Dateien.

### D.2 Ternäres `fact`-Schema (im Translator-Modul-Docstring 1:1 fixiert)

`src/pyirk/nemobridge/translator.py:14-34` (Header-Docstring):

```
@import triples :- csv{resource="triples.csv", format=(string,string,string)} .
fact(?s, ?p, ?o) :- triples(?s, ?p, ?o) .

% Direct (R1-type)
fact(?s, "irk:/builtins#R83", ?o) :- fact(?s, "irk:/builtins#R3", ?o) .

% Transitive (R2-type)
is_transitive("irk:/builtins#R17") .
fact(?s, ?p, ?o) :- is_transitive(?p), fact(?s, ?p, ?x), fact(?x, ?p, ?o) .

@export fact :- csv{resource="output_fact.csv"} .
```

Implementierungs-Header in `generate_rls(ds, …)`
(`translator.py:291-333`) — vor allem `:309` (`@import triples :-
csv{resource="triples.csv", format=(string,string,string)} .`) und `:331`
(`@export fact :- csv{resource="output_fact.csv"} .`).

### D.3 Spike-Belege (Phase-0-Fundament)

`docs/design/h5_spike_report.md:42-46` (R1-Übersetzung mit binärem
Output) und `:60-66` (R2 mit `trans/3` rekursiv) zeigen, dass das **alte**
binäre Schema durch das ternäre `fact`-Modell ersetzt wurde, weil binär die
Modul-Kollision in `short_key`s nicht überlebt (vgl. Phase-2-Gate-1-Bug,
`docs/design/h5_phase2_report.md:120-142`).

---

## E) Regel-Inventar `tests/test_data/zebra_puzzle_rules.py`

> Klassifikations-Stand aus dem Recon-Lauf (siehe §F.3):
> `direct=4, transitive=1, python_only=24` von 29 Regeln im Zebra-Set.
> Reasons hier so wiedergegeben, wie sie der aktuelle Translator liefert,
> mit einer h5-Extension-Einordnung.

### E.1 Literal-Prämissen

#### I702 — `rule: add reverse statement for symmetrical relations`
`zebra_puzzle_rules.py:43-56`. Prämisse (`:52-53`):

```python
with I702.scope("premise") as cm:
    cm.new_rel(cm.rel1, p.R42["is symmetrical"], True)
```

- **Literal-Datentyp:** `bool` (`True`) als Objekt von `R42`.
- **Prämisse vs. Konklusion:** Literal lebt in der Prämisse; die Konklusion
  ist ein Consequent-Callback (`reverse_statements`, Python-only).
- **Würde der vorgeschlagene Literal-Exporter reichen?** Nein — selbst wenn
  Literale exportiert werden, ist die Konklusion ein Python-Callback. Regel
  bleibt `python_only`.

#### I705 — `rule: deduce trivial different-from-facts`
`zebra_puzzle_rules.py:61-83`. Prämisse (`:73-78`):

```python
with I705.scope("premise") as cm:
    cm.new_rel(cm.p1, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p2, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p1, p.R57["is placeholder"], False)
    cm.new_rel(cm.p2, p.R57["is placeholder"], False)
```

- **Literal-Datentyp:** `bool` (`False`) als R57-Objekt.
- **Prämisse vs. Konklusion:** Literal nur in der Prämisse; Konklusion ist
  pures Tripel (`R50["is different from"]` mit qualifier ptg_mode=5,
  `:82-83`).
- **Reicht ein Literal-Exporter?** Hier möglicherweise ja — die Prämisse
  besteht nur aus Tripeln (zwei Entities-Tripel über `R4`, zwei
  Literal-Tripel über `R57=False`); die Konklusion ist auch ein Tripel.
  Wenn der Exporter `(s, R57, "False"^^bool)` als Datenterm in `triples.csv`
  schreibt und Nemo das per Equality-Constant joinen kann, ließe sich I705
  delegieren — modulo Qualifier-Reifikation der Konklusion (V1).

#### I790 — `rule: infer from 'is one of' -> 'is same as'`
`zebra_puzzle_rules.py:505-522`. Prämisse (`:516-519`):

```python
with I790.scope("premise") as cm:
    cm.new_rel(cm.itm1, p.R56["is one of"], cm.tup1)
    cm.new_rel(cm.tup1, p.R38["has length"], 1)
    cm.new_rel(cm.tup1, p.R39["has element"], cm.elt0)
```

- **Literal-Datentyp:** `int` (`1`) als R38-Objekt.
- **Konklusion** (`:521-522`): reines Tripel `(elt0, R47, itm1)`.
- **Reicht ein Literal-Exporter?** Ja, das ist der „goldene" Fall: eine
  Literal-Bedingung über eine ground-term-Konstante (`R38=1`). Mit
  Literal-Export ließe sich der Body als
  `fact(?itm1, "…R56", ?tup1), fact(?tup1, "…R38", 1), fact(?tup1, "…R39",
  ?elt0)` schreiben. **Voraussetzung:** Nemo akzeptiert Mischtypen in
  `fact`-Spalten (`string,string,string` reicht nicht, `R38=1` wäre Integer).
  Praktisch heißt das: eigener Predikatpfad für Literal-Tupel oder konsequent
  `string` mit Repr-Konvertierung (`"1"`).

#### I800 — `rule: mark relations which are opposite of functional activities`
`zebra_puzzle_rules.py:744-765`. Prämisse (`:754-756`):

```python
with I800.scope("premise") as cm:
    cm.new_rel(cm.rel1_not, p.R43["is opposite of"], cm.rel1)
    cm.new_rel(cm.rel1, zb.R2850["is functional activity"], True)
```

- **Literal-Datentyp:** `bool` (`True`) als Objekt von `zb.R2850`.
- **Konklusion** (`:758-765`): zwei Tripel `(rel1_not, R6020, True)` und
  `(rel1_not, R71, True)` — Konklusion hat selbst Literal-Werte (`True`).
- **Reicht ein Literal-Exporter?** Möglich — falls auch Konklusionen mit
  Literal-Objekt zugelassen werden (heute nicht: B.1 verwirft Literale auch
  im Export). Erfordert symmetrische Behandlung Prämisse↔Konklusion.

#### I820 — `rule: deduce personhood by exclusion`
`zebra_puzzle_rules.py:857-916`. Prämisse (`:893-913`): viele
`R4__is_instance_of zb.I7435["human"]` (sechs Mal) + Literal-Tripel
`(p0, R57, True)`, `(p1..p5, R57, False)` + `R50__is_different_from`.

- **Literal-Datentyp:** `bool` (`True`/`False`).
- **Konklusion** (`:915-916`): reines Tripel `(p0, R47, p5)`.
- **Reicht ein Literal-Exporter?** Strukturell ja — die Prämisse hat keine
  Callbacks/SPARQL/OR. **Aber:** Die Prämisse hat **6 Var-Quantoren über
  Humans** plus mehrere R50-Ketten — das ist ein Großes Join-Problem, aber
  formell ein BGP. Mit Literal-Export wäre das die größte gewonnene
  Zebra-Regel.

### E.2 OR-Subscope

#### I720 — `rule: replace (some) same_as-items`
`zebra_puzzle_rules.py:133-171`. Prämisse (`:144-167`):

```python
with I720.scope("premise") as cm:
    cm.new_rel(cm.itm1, p.R47["is same as"], cm.itm2)
    cm.new_rel(cm.itm2, p.R57["is placeholder"], True)

    with cm.OR() as cm_OR:
        # case 1: both are placeholders (- then itm1 must be alphabetically smaller)
        with cm_OR.AND() as cm_AND:
            cm_AND.new_rel(cm.itm1, p.R57["is placeholder"], True)
            cm_AND.new_condition_func(p.label_compare_method, cm.itm1, cm.itm2)
        # case 2: itm1 is not a placeholder (no statement)
        with cm_OR.AND() as cm_AND:
            cm_AND.new_condition_func(p.does_not_have_relation, cm.itm1, p.R57["is placeholder"])
        # case 3: itm1 is not a placeholder (explicit statement with object `False`)
        cm_OR.new_rel(cm.itm1, p.R57["is placeholder"], False, qualifiers=[…])
```

Form der OR-Verzweigung im DSL: **`with cm.OR() as cm_OR` als Sub-Scope**;
innen drei AND-Branches (zwei via `with cm_OR.AND() as cm_AND`, eine
direkter `cm_OR.new_rel`). Branches enthalten Mischformen:
Literal-Statements (`R57=True/False`) und Condition-Funktionen
(`label_compare_method`, `does_not_have_relation`).
**Klassifikation:** `python_only` mit Reason `"OR-subscope in premise —
branching not translatable to Datalog"` (`translator.py:146`). Selbst eine
trianguläre Disjunktions-Erweiterung des Translators (Hypothese §C.3) wäre
hier blockiert, weil die OR-Branches ihrerseits Python-Callbacks führen
(`new_condition_func`).

### E.3 SPARQL-Prämissen

> Einordnungsschema je Regel: **reines BGP / BGP+stratifizierte Negation /
> nicht-übersetzbar**. Bei Unsicherheit → nicht-übersetzbar mit Begründung.

#### I710 — `rule: identify same items via R2850__is_functional_activity`
`zebra_puzzle_rules.py:89-128`. SPARQL (`:104-112`):

```sparql
WHERE {
?p1 ?rel1 ?some_itm.
?p2 ?rel1 ?some_itm.

?rel1 zb:R2850 true.      # R2850__is_functional_activity
FILTER (?p1 != ?p2)
}
```

- **Muster:** reines BGP + Literal-Filter (`R2850=true`) + `FILTER`-Inequality.
- **Einordnung:** **reines BGP** (mit Literal-Konstante und Inequality). Die
  Inequality `?p1 != ?p2` ist in Datalog per Disjunktion über zwei
  separate ground-checks NICHT direkt ausdrückbar, aber Nemo unterstützt
  Built-in-Predicates für Vergleiche (`!=`). Tendenziell delegierbar; Risiko:
  je nach Nemo-0.10-Subset.
- **Konklusion** (`:123-124`): reines Tripel `(p1, R47, p2)`.

#### I725 — `rule: deduce facts from inverse relations`
`zebra_puzzle_rules.py:175-203`. SPARQL (`:189-196`):

```sparql
WHERE {
    ?itm1 ?rel1 ?itm2.
    ?rel1 :R68 ?rel2.        # R68__is_inverse_of
}
```

- **Muster:** reines BGP (zwei Tripel, keine Filter).
- **Einordnung:** **reines BGP** → in das `fact`-Modell direkt übersetzbar
  (`fact(?itm2, ?rel2, ?itm1) :- fact(?itm1, ?rel1, ?itm2), fact(?rel1,
  "…R68", ?rel2) .`). **Aber:** `?rel1` und `?rel2` sind Prädikat-Variablen
  — das passt in das ternäre Modell, weil Prädikate Datenwerte sind.
  Die Konklusion ist ein reines Tripel (mit Qualifier-Mode 5; siehe V1).
- **Delegations-Hindernis nur:** Qualifier-Vermeidung in der Konklusion
  (V1 vertagt).

#### I730 — `rule: deduce negative facts for neighbors`
`zebra_puzzle_rules.py:207-234`. SPARQL (`:222-230`): vier Tripel,
keine Filter, eine Literal-Konstante (`R2850 true`).
- **Einordnung:** **reines BGP** + Literal-Konstante. Wie I725 strukturell
  delegierbar, sobald Literale exportiert werden.

#### I740 — `rule: deduce more negative facts from negative facts`
`zebra_puzzle_rules.py:238-280`. SPARQL (`:257-279`): **6 Tripel + 5
FILTER-Inequalities + 1 Literal-Konstante**. Auskommentiert: `MINUS { ?h2
?rel1_not ?itm1.}` — der MINUS ist im aktiven Skript inaktiv.
- **Einordnung:** **reines BGP** + viele Inequalities. Delegierbar
  konditional auf Nemo-Built-in-`!=`.

#### I741 — `rule: deduce more negative facts from negative facts` (Variante)
`zebra_puzzle_rules.py:529-579`. SPARQL (`:548-575`): **8 Tripel + 5
FILTER-Inequalities + 2 Literal-Konstanten** (`R57 false`) + aktiver
`MINUS { ?itm2 :R57 true.}`.
- **Einordnung:** **BGP + stratifizierte Negation** (das aktive `MINUS`
  über `?itm2 :R57 true.` ist klassische stratifizierte Negation). Nemo
  0.10 unterstützt Negation-as-Failure für stratifizierbare Programme;
  delegierbar, falls die Stratifikation global aufgeht.

#### I792 — `rule: deduce different-from-facts from negative facts`
`zebra_puzzle_rules.py:587-625`. SPARQL (`:603-616`): 7 Tripel,
3 Literal-Konstanten (`R4=I7435`, `R57=false`, `R2850=true`), keine Filter,
keine MINUS.
- **Einordnung:** **reines BGP** (mit ground-Konstanten als Literale).
  Delegierbar sobald Literale fließen.

#### I798 — `rule: deduce negative facts from different-from-facts`
`zebra_puzzle_rules.py:708-735`. SPARQL (`:723-732`): 4 Tripel + 1
Literal (`R2850 true`), keine FILTER.
- **Einordnung:** **reines BGP** + Literal. Strukturell der einfachste
  delegierbare SPARQL-Fall.

#### I803 — `rule: deduce different-from-facts from functional activities`
`zebra_puzzle_rules.py:771-801`. SPARQL (`:787-801`): 7 Tripel +
2 Literal-Konstanten (`R57 false`) + 1 FILTER-Inequality.
- **Einordnung:** **reines BGP** + Inequalities. Hat eine Tuple-Membership-
  Kette (`type→R51→tuple→R39→itm2`) — strukturell reine Joins, problemlos
  in Datalog. Delegierbar.

#### Zusammenfassung SPARQL-Buckets

| Regel | Bucket | Hinweise |
|---|---|---|
| I710 | reines BGP | Inequality, Nemo `!=` nötig |
| I725 | reines BGP | sauberster Inverse-Pattern |
| I730 | reines BGP | + Literal |
| I740 | reines BGP | + 5× Inequality |
| I741 | BGP + strat. Negation | aktives MINUS |
| I792 | reines BGP | + Literale |
| I798 | reines BGP | klein |
| I803 | reines BGP | + Inequality |

Keine Regel im SPARQL-Set ist hier konservativ auf „nicht-übersetzbar"
gesetzt — alle aktiven Konstrukte (BGP, Literal-Konstante, FILTER `!=`,
stratifizierter MINUS) sind in Datalog-Erweiterungen modellierbar.
**Risiko:** Konkrete Subset-Verfügbarkeit in Nemo 0.10 ist nicht hier
verifiziert (kein Tool-Lauf).

---

## F) Bestehende Tests / Baselines

### F.1 Wie wird `equivalence_gate.py` aufgerufen?

Aus dem Modul-Docstring (`experiments/h5_phase2/equivalence_gate.py:22-25`):

```
/home/user/venvs/pyirk-core-venv/bin/python \
    experiments/h5_phase2/equivalence_gate.py \
    2>&1 | tee experiments/h5_phase2/equivalence_gate.log
```

Exit-Codes (`equivalence_gate.py:27-30`): `0` = alle drei Gates ok,
`1` = mindestens ein Gate failed, `2` = Infrastruktur (kein Nemo-Binary,
kein OCSE).

Hartcodierte Pfade im Skript: `NEMO_BIN = "/home/user/bin/nmo"`
(`:48`), `OCSE_DIR = "/home/user/projekte/irk-data/ocse"` (`:49`),
`VENV_PYTHON = "/home/user/venvs/pyirk-core-venv/bin/python"` (`:52`).
Optional: `--keep-snapshots` (`:318-321`).

### F.2 Flag-Name `PYIRK_NEMO_DELEGATION` — Lesepfad

- **Lese-Stelle:** `src/pyirk/ruleengine.py:91`
  ```python
  if os.environ.get("PYIRK_NEMO_DELEGATION"):
  ```
  innerhalb von `apply_semantic_rules(*rules, mod_context_uri=None,
  exhaust=False)` (`ruleengine.py:67`). Default: **AUS** — ohne Env-Var
  läuft alles nativ (`docs/design/performance.md:147`).
- **Hilfsfaktoren im Delegationspfad:** `PYIRK_NEMO_BIN` als Override für
  das Nemo-Binary (`src/pyirk/nemobridge/delegation.py:38` in
  `_nemo_available()` und `:116` in `_apply_via_nemo`).
- **Test-Subprocess** setzt/löscht die Env-Var explizit vor dem
  pyirk-Import (`experiments/h5_phase2/equivalence_gate.py:103-106`).

### F.3 Wie viele Regeln werden derzeit auf den Zebra-Regeln delegiert?

Lokaler Recon-Lauf (`/home/user/venvs/pyirk-core-venv/bin/python -c …`)
gegen `tests/test_data/zebra_puzzle_rules.py` (lädt `zebra_base_data.py`
mit, dann `classify_rules(p.ds)`):

```
TOTAL_RULES: 29
BY_CAT: {'direct': 4, 'transitive': 1, 'python_only': 24}
```

Vollständige Aufschlüsselung der 29 Regeln:

| Key | Kategorie | Reason (Auszug) |
|---|---|---|
| I64 | direct | Pure triple-pattern premise/assertion |
| I65 | direct | Pure triple-pattern premise/assertion |
| I66 | transitive | R60 + R58 wildcard |
| I701 | python_only | Assertion creates new entities (fiat) |
| I702 | python_only | Literal in premise (`R42=True`) |
| I705 | python_only | Literals in premise (`R57=False` ×2) |
| I710 | python_only | SPARQL premise |
| I720 | python_only | OR-subscope |
| I725 | python_only | SPARQL premise |
| I730 | python_only | SPARQL premise |
| I740 | python_only | SPARQL premise |
| I750 | python_only | Condition-callback anchor |
| I760 | python_only | Assertion creates new entities (fiat) |
| **I763** | **direct** | Pure triple-pattern premise/assertion |
| I770 | python_only | Assertion creates new entities (fiat) |
| I780 | python_only | Assertion creates new entities (fiat) |
| I790 | python_only | Literal in premise (`R38=1`) |
| I741 | python_only | SPARQL premise |
| I792 | python_only | SPARQL premise |
| I794 | python_only | Condition-callback anchor |
| **I796** | **direct** | Pure triple-pattern premise/assertion |
| I798 | python_only | SPARQL premise |
| I800 | python_only | Literal in premise (`R2850=True`) |
| I803 | python_only | SPARQL premise |
| I820 | python_only | Literals in premise (`R57=True/False` ×4) |
| I810 | python_only | Cheat |
| I830 | python_only | Cheat |
| I840 | python_only | Cheat |
| I825 | python_only | Assertion creates new entities (fiat) |

Damit sind **5 von 29** Zebra-Regeln derzeit delegierbar: **I64, I65, I66,
I763, I796** (4× direct, 1× transitive). Die übrigen 24 sind blockiert
durch SPARQL (8), Literal-Prämisse (5), fiat-Konklusion (6),
Condition-Callback (2), OR-Subscope (1), Cheat (3).

**Offene Frage:** Sind I64, I65, I66 die nativen pyirk-Builtin-Regeln
(`src/pyirk/builtin_entities.py` aus dem Phase-1-Bericht), die vom
Zebra-Modul mitgeladen werden, oder Zebra-eigene? Im Phase-1-Report
`docs/design/h5_phase1_report.md:166-175` figurieren genau I64/I65/I66
(und zusätzlich I4731) als die OCSE-delegierbaren Regeln — d. h. auf
einer KB ohne Zebra-spezifische Regeln. Daher: I64/I65/I66 sind builtin
und werden hier mitgezählt; **Zebra-eigene Beiträge zum delegierbaren
Set sind nur I763 und I796**.

---

## Recon-Zusammenfassung

- **Klassifikator** sitzt mono in `src/pyirk/nemobridge/translator.py:119-204`,
  mit 8 klar geordneten `python_only`-Gates.
- **Exporter** filtert Literal-Objekte konsequent in **beiden** Export-Pfaden
  (`exporter.py:249-250` und `:169-170`), hängt aber `stmts.csv`/`quals_*.csv`
  + `uri_index.csv`-Sidecar an `triples.csv` an — alles in Phase 2.1 mit
  vollen URIs in den Daten-Spalten.
- **Translator** kodiert ternär (`fact(?s,?p,?o)`), Prädikate sind URI-Strings
  (`format=(string,…)`), Output ist genau eine Datei `output_fact.csv`.
- **Nemo-Encoding** ist seit Phase 2.1 stabil verankert in
  `docs/design/performance.md:146-150` und `h5_phase2_report.md:256-265`.
- **Zebra-Bestand:** 5/29 delegierbar — die Erweiterungs-Hebel laut goal.md
  liegen bei **Literal-Export** (würde I702/I705/I790/I800/I820 entlasten —
  davon I705/I790/I820 strukturell gewinnbar) und **SPARQL→Datalog**
  (würde I710/I725/I730/I740/I741/I792/I798/I803 freischalten; I725/I798
  sind die niedrig hängenden Früchte).
- **OR-Subscope** (I720): blockiert nicht nur durch die OR-Form selbst,
  sondern auch durch eingebettete Condition-Callbacks — selbst eine
  Disjunktions-Erweiterung des Translators löst I720 nicht ohne zusätzlichen
  Callback-Pfad.
