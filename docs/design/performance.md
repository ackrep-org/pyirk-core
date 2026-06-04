# Designdokument: Performance von pyirk

> Status: Entwurf (2026-05-25), unterlegt mit echten Profiling-Zahlen aus der OCSE-Testsuite.
> Leitprinzip: **Ausdrucksstärke und Features bleiben unangetastet.** Optimiert wird das
> *Substrat* hinter der stabilen öffentlichen API — nicht die Modellierungssemantik.

## 1. Motivation & Befund

Beobachtetes Problem: ab einer gewissen Statement-Anzahl wird pyirk spürbar langsam.
Performance wurde bisher bewusst zugunsten der Ausdrucksstärke zurückgestellt.

Messung an der realen OCSE-Wissensbasis (`irk-data/ocse`, ~5190 Zeilen / ~400 `create_item`
über `agents1.py` + `math1.py` + `control_theory1.py`), Python 3.11, Consistency-Checking aktiv:

| Suite | Gesamt | Auffälligstes |
|---|---|---|
| `tests/test_quick.py` (6 Tests) | 18,4 s | fixer Overhead ~2,6 s/Test (selbst der reine Versions-Test) |
| `tests/test_package.py` (13 Tests) | 61,3 s | `test_e01__element_type_rule` **38,5 s**, `test_c07__cc_theorem_application` **8,75 s**; alle übrigen < 1 s |

### Profiling des 38-s-Tests (cProfile, relative Werte)

```
ncalls       tottime  cumtime  Funktion
3.912.926      4.95     6.26    auxiliary.py:378  ensure_valid_baseuri
564.712        4.31    30.12    _core/keymanager.py:115  process_key_str
1.533.694      3.50     7.14    auxiliary.py:305  ensure_valid_uri
2.379.229      3.36     7.88    auxiliary.py:399  make_uri
486.731        2.85    23.94    core.py:311  _get_relation_contents
1.852.141      2.36     2.76    ruleengine.py:951  _node_matcher
542.537        1.12    33.70    core.py:209  __getattr__   (cumulativ größter Posten)
542.569        0.67    28.02    core.py:237  __process_attribute_name
15.069         0.08    20.95    _builtin/taxonomy.py:97  get_taxonomy_tree
```

**Kernbefund:** Der Engpass ist *nicht* die Reasoning-Logik, sondern **Overhead pro Zugriff
im Substrat**, millionenfach getrieben durch die dynamische Attributauflösung
(`item.R4__is_instance_of`) und durch Validierungsfunktionen, die auf jedem Lesepfad laufen.
Die Rule-Engine (`_node_matcher`) ist sekundär — sie *verstärkt* nur diesen Overhead, indem
sie ihn millionenfach auslöst.

## 2. Ziele / Non-Goals

- **Ziel:** signifikante Beschleunigung **ohne** Feature- oder Ausdrucksstärke-Verlust und
  **ohne** Änderung der öffentlichen oder internen API-Signaturen.
- **Ziel:** schnell *mit* aktivem Consistency-Checking (nicht nur im abgeschalteten Modus).
- **Non-Goal (vorerst):** Neuschreiben der Rule-Engine; Umstieg auf einen externen Reasoner.
  Das ist ein späterer, größerer Hebel (siehe Phase 4), nicht der erste Schritt.
- **Non-Goal:** Semantik von Funktionalität (R22/R32), Multilingualität, Scopes etc. anfassen.

## 3. Hebel (nach ROI sortiert)

### H1 — Validierung von den Lesepfaden entfernen  (größter, billigster Gewinn)
Korrektheits-Checks (`ensure_valid_uri`, `ensure_valid_baseuri`, `ensure_valid_short_key`,
`make_uri`) sind reine String-/Regex-Prüfungen und laufen **millionenfach beim Lesen**
(`_get_relation_contents` ruft `ensure_valid_uri` pro Zugriff; `make_uri` ruft
`ensure_valid_baseuri` pro URI-Bau). Diese Daten wurden bereits bei der *Erzeugung* validiert.
Maßnahmen:
- (a) **Regex-Vorkompilierung:** `ensure_valid_short_key` (auxiliary.py:282) kompiliert seine
  Regex bei *jedem* Aufruf neu (~508k mal). Auf Modulebene ziehen — isolierter Soforteffekt.
- (b) **Validierung hinter `assert`/`__debug__`** stellen — exakt das Muster, das `core.py`
  bei `check_type` schon nutzt (abschaltbar via `python -O`). Auf Lesepfaden Checks nur im
  Debug-Lauf.
- (c) **Validierung an die Schreib-/Erzeugungsgrenze verschieben** (einmal bei `create_*`/
  `set_relation`), nicht bei jedem `__getattr__`.
- Kein Cache-Invalidierungs-Problem, da reine Funktions-Skips.

### H2 — Attributauflösung memoisieren
`__getattr__` → `__process_attribute_name` → `process_key_str` re-parst denselben Label-String
bei jedem Zugriff (cumtime ~30 s). Die Strings ("R4__is_instance_of", …) wiederholen sich
ständig. Maßnahme: ein Cache `attr_name -> ProcessedStmtKey` (Dict / `functools.lru_cache`).
URIs/Keys sind unveränderlich → sicher. **Invalidierung:** nur nötig, wenn neue Relationen mit
neuen Labels definiert werden (Cache leeren bei `create_relation`); keine negativen Lookups
cachen.

### H3 — Taxonomie-/Subklassen-Closure cachen
`get_taxonomy_tree` / `is_subclass_of` werden unter der Rule-Engine wiederholt neu berechnet
(15k Aufrufe, cumtime ~21 s). Maßnahme: memoisierte Subklassen-/Instanz-Closure im DataStore.
**Invalidierung:** gezielt bei Änderung von R3/R4-Statements (Hook in `set_relation`/
`_unlink_entity`). Verwandeln wiederholte O(Tiefe·Breite)-Walks in O(1)-Lookups.

### H4 — Indexierungs-Layer im DataStore (API-erhaltend)
Falls Query-Funktionen (`get_statements`, `get_relations`, `get_all_instances_of`) intern
linear scannen: echte Indizes (`(subject,predicate) -> stmts`, Rückwärts-Index nach Objekt,
Typ-Index). Die Außenseite bleibt unverändert. Profiling nach H1–H3 entscheidet, ob nötig.

### H5 (später, großer Hebel) — Reasoning inkrementell oder hybrid
Erst nachdem H1–H4 das Substrat entlastet haben:
- **Inkrementell/materialisiert** (RETE-artig): abgeleitete Statements cachen, gezielt
  invalidieren.
- **Hybrid** mit `rdfstack.py` / der `sparql_reasoning`-Branch: den entscheidbaren Anteil
  (OWL-RL/SPARQL) an einen reifen Reasoner delegieren, den ausdrucksstärkeren Rest in Python.

## 4. Vorgehen (Phasen — Phase 1 ist der `goal.md`-Kandidat für einen autonomen Lauf)

- **Phase 0 — Benchmark-Harness.** Reproduzierbares Skript: (i) `test_quick`/`test_package`-
  Zeiten, (ii) isolierte Modul-Ladezeit mit/ohne Consistency-Checking, (iii) synthetisches
  Modul, das die Statement-Zahl skaliert (1k/10k/100k). Liefert die Regressionsbasis und macht
  jede Optimierung messbar. **Akzeptanz:** ein Befehl, der eine Kennzahl-Tabelle ausgibt.
- **Phase 1 — H1 (Validierung) + H2 (Attr-Cache).** Erwartung: der Großteil der ~30 s
  `process_key_str`-cumtime und der Validierungs-tottime fällt weg. Reine Interna,
  Testsuite (pyirk-core + OCSE) als Sicherheitsnetz, keine API-Änderung.
- **Phase 2 — H3 (Closure-Cache)** inkl. sauberer Invalidierung.
- **Phase 3 — H4 (Indizes), nur wenn Profiling es nach Phase 2 noch zeigt.**
- **Phase 4 — H5 (Reasoning), separate Entscheidung** (rein-Python inkrementell vs. Hybrid).

## 4b. Messergebnis: `python -O` / `PYTHONOPTIMIZE=1` (2026-06-04)

Nach dem assert-Audit (alle tragenden asserts → explizite raises, Suite unter `-O` grün) wurde
der `-O`-Effekt sauber gemessen: VPS exklusiv (load ≈ 0), `tools/perf_benchmark.py --reps 3
--skip-profile` (best-of-3), einmal normal, einmal mit `PYTHONOPTIMIZE=1`. Wichtig:
`PYTHONOPTIMIZE=1` statt `python -O`, weil das Harness Subprozesse startet und `-O` nicht an
Kindprozesse vererbt wird.

| Messung                          | normal  | optimiert | Δ      |
|----------------------------------|---------|-----------|--------|
| OCSE-Load (CC on)                | 3.20 s  | 2.50 s    | −22 %  |
| OCSE-Load (CC off)               | 3.01 s  | 2.25 s    | −25 %  |
| OCSE test_package.py (Suite)     | 13.3 s  | 11.3 s    | −15 %  |
| test_e01 (rule-engine-dominiert) | 35.9 s  | 35.1 s    | −2 %   |
| test_c07 (Theorem-Anwendung)     | 6.9 s   | 6.4 s     | −7 %   |
| 10 000 Items create              | 4.31 s  | 2.97 s    | −31 %  |
| 10 000 Items query               | 0.53 s  | 0.32 s    | −39 %  |

**Fazit:** H1(b) zahlt sich wie erhofft aus — `-O` strippt die hinter `assert`/`__debug__`
gelegte Lesepfad-Validierung und bringt 30–40 % in den heißen Pfaden sowie ~25 % beim
Modul-Load. Für große Loads ist `PYTHONOPTIMIZE=1` damit empfehlenswert. Die Rule Engine
(test_e01) profitiert kaum; weiteres Potenzial dort liegt bei H5.

## 5. Risiken & offene Punkte

- **Cache-Invalidierung** ist die Hauptgefahr (H2/H3): pyirk mutiert den DataStore (Entities
  unload, Statements ändern). Jeder Cache braucht einen klaren Invalidierungs-Hook; die
  Testsuite muss das absichern. H1 ist risikolos (nur Arbeit auslassen).
- **Messmethodik:** cProfile verzerrt Absolutzeiten (160 s vs. 38 s real); nur relative Werte
  und Wall-Clock-Benchmarks (Phase 0) zur Bewertung nutzen.
- **Korrektheits-Auffälligkeit (separat, nicht Performance):** `test_e01__element_type_rule`
  meldet "Unexpected success" (als `expectedFailure` markiert, besteht aber jetzt). Vor
  Optimierungen klären, ob das ein veralteter OCSE-Test ist oder eine Verhaltensänderung —
  sonst ist die Regressionsbasis unscharf.
- **Voraussetzung erfüllt:** das kürzliche Fassaden-Refactoring (`_core/`, `_builtin/`) macht
  diese Substrat-Eingriffe überhaupt erst sicher durchführbar (klare Modulgrenzen + grüne
  Tests als Netz).
