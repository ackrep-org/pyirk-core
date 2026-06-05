# H5-Spike: Delegierbarkeit pyirk-Regeln an externe Rust-Engine

## Zusammenfassung

Der Spike zeigt, dass pyirk-Regeln vom Typ R1 (reine Tripel-Praemisse) und R2 (Transitivitaets-
Propagierung) korrekt an die Nemo-Rust-Engine delegiert werden koennen. Beide Korrektheitschecks
bestaetigten exakte Uebereinstimmung mit der pyirk-Referenzausgabe. Der Speedup ist erheblich:
Faktor ~16x fuer R1 und >1000x fuer R2, selbst unter Beruecksichtigung des vollstaendigen
Export/Run/Import-Overheads.

## Profiling-Kontext

Aus dem Vorgaenger-Spike (Branch h5_profiling): Die Rule Engine verbringt 86,5 % der
Laufzeit im VF2-Subgraph-Isomorphismus-Matching (29,9 s bei 482 736 Rekursionen). Eine
externe Engine muss dieses Matching ersetzen, um relevant zu sein.

## Setup

- Engine: Nemo v0.10.0 (Binary `/tmp/nmo`, Linux amd64, musl-linked)
- Anbindung: Subprozess (CLI `nmo`), Fakten als CSV, Regeln als .rls-Datei
- Test-KB: 9 Entitaeten (I1001-I1009) + 1 transitive Relation (R1001) aus `create_test_kb.py`.
  Davon bilden I1001-I1005 eine R3-Subklassen-Hierarchie (4 direkte Kanten), und
  I1006-I1009 eine 3-Hop-Kette ueber R1001. Beim Export werden zusaetzlich alle builtin
  R3-Fakten (49 Zeilen gesamt) aus dem pyirk-DataStore mitexportiert.
- venv: `/tmp/pyirk-core-venv`

## Ausgewaehlte Spike-Regeln

| Regelname | Typ | Quelle | Beschreibung | Delegierbar? |
|-----------|-----|--------|--------------|-------------|
| R1 = I64 | Reine Tripel-Praemisse | `src/pyirk/builtin_entities.py` | R3 -> R83 (is_subclass_of -> is_generalized_subclass_of) | Ja |
| R2 = I66 | Wildcard-Relation | `src/pyirk/builtin_entities.py` | Transitivitaets-Propagierung | Bedingt (statische Rel.-Liste) |
| R3 = I794 | Python-Callback/Lambda | `tests/test_data/zebra_puzzle_rules.py` | y == x+1 in Praemisse | Nein |

## Uebersetzungsschema

### R1 (I64): pyirk -> Nemo

pyirk-Regel I64 besagt: fuer alle `(i2, R3__is_subclass_of, i1)` erzeuge `(i2, R83__is_generalized_subclass_of, i1)`.

Uebersetzung in `rules_r1.rls`:
```
@import is_subclass_of :- csv{resource="facts_for_r1.csv"} .
is_generalized_subclass(?i2, ?i1) :- is_subclass_of(?i2, ?i1) .
@export is_generalized_subclass :- csv{resource="output_r1.csv"} .
```

Der Exporter `export_r3_facts()` schreibt alle R3-Tripel (Subjekt-Key, Objekt-Key) in eine
2-spaltige CSV. Nemo liest diese und erzeugt eine identische 2-spaltige Ausgabe fuer R83.
Scope-Items (Entitaeten mit `R20__has_defining_scope`) werden herausgefiltert, da sie nicht
als eigenstaendige Fakten sinnvoll sind.

### R2 (I66): pyirk -> Nemo (bedingt)

pyirk-Regel I66 berechnet die transitive Huelle aller als transitiv markierten Relationen
bis zur Saettigung.

Uebersetzung in `rules_r2.rls` (rekursiver Datalog):
```
@import base_triple :- csv{resource="facts_for_r2.csv"} .
is_transitive(R1001) .
trans(?s, ?p, ?o) :- base_triple(?s, ?p, ?o) .
trans(?i1, ?r, ?i3) :- is_transitive(?r), trans(?i1, ?r, ?i2), trans(?i2, ?r, ?i3) .
@export trans :- csv{resource="output_r2_new.csv"} .
```

**Einschraenkung**: Die `is_transitive(...)` Fakten muessen statisch aufgelistet werden, da
Nemo keine Praedikat-Variablen in Regelkoepfen unterstuetzt. Bei pyirk wird die Transitivitaet
dynamisch per `R60__is_transitive=True` auf einer Relation markiert. Der Hybrid-Ansatz benoetigt
einen Code-Generator, der pyirk-Relationen mit R60 scannt und is_transitive-Fakten generiert.

## Korrektheitsabgleich

Beide Regeln wurden auf der Test-KB exakt validiert:

- R1 (I64): **OK** -- 49 Statements in pyirk-Baseline (gefiltert), 49 von Nemo abgeleitet, identisch
- R2 (I66): **OK** -- 6 Statements (3 Basisfakten + 3 abgeleitete, inkl. 3-Hop I1006->I1009),
  identisch mit pyirk exhaust-Lauf

## Timing

| Variante | Lauf 1 (s) | Lauf 2 (s) | Lauf 3 (s) | Best-of-3 (s) |
|----------|-----------|-----------|-----------|---------------|
| pyirk I64 | 0.2048 | 0.2141 | 0.1996 | 0.1996 |
| Nemo R1 (Export+Run+Import) | 0.0128 | 0.0137 | 0.0147 | 0.0128 |
| pyirk I66 (exhaust) | 8.9715 | 9.0529 | 8.5481 | 8.5481 |
| Nemo R2 (Export+Run+Import) | 0.0067 | 0.0071 | 0.0069 | 0.0067 |

**Speedup**: R1-Typ ~15.6x (0.20s -> 0.013s), R2-Typ ~1276x (8.55s -> 0.0067s).
Der Nemo-Overhead (CSV-Export + Subprozess-Start + CSV-Import) betraegt ca. 6-15 ms
und ist bei Regellaeufen > 20ms bereits amortisiert. Der extreme Speedup bei R2 bestaetigt
den h5_profiling-Befund: Das VF2-Matching in pyirk's Transitivitaetsregel ist der
dominante Flaschenhals.

## Delegierbarkeits-Bestand

| Kategorie | Anzahl | Anteil | Beispiele |
|-----------|--------|--------|-----------|
| Direkt delegierbar (R1-Typ) | 14 | 41 % | I64, I65, I901, I902 |
| Bedingt delegierbar (R2-Typ, statische Liste) | 11 | 32 % | I66, I710, I725 |
| Nicht delegierbar (R3-Typ, Python-Callback) | 9 | 27 % | I794, I903, I905 |
| **Gesamt** | **34** | **100 %** | |

## Fixpunkt-Frage

Die 25 delegierbaren Regeln (R1-Typ + R2-Typ) koennen prinzipiell gemeinsam in Nemo
bis zur Saettigung laufen, da Nemo als Datalog-Engine nativ Fixpunkt-Semantik implementiert.
Voraussetzung: alle Praemissen-Fakten werden in einem gemeinsamen EDB gebundelt, und die
is_transitive-Fakten werden per Code-Generator aus pyirk extrahiert. Die 9 Python-Callback-
Regeln muessen weiterhin in pyirk laufen; Wechselwirkungen (wenn Callback-Regeln neue Fakten
erzeugen, die Nemo-Regeln als Praemissen brauchen) erfordern eine definierte Ausfuehrungsreihenfolge
oder mehrere Nemo-Laeufe mit Rueckkopplung.

## Risiken

1. **Scope-Item-Filter-Luecke**: Der Exporter muss Scope-Items herausfiltern (hat `R20__has_defining_scope`),
   da diese keine eigenstaendigen Fakten darstellen. Die Regel I64 in pyirk behandelt dagegen
   ALLE R3-Fakten inkl. Scope-Items. Bei zunehmend komplexen Scope-Strukturen koennte die
   Filterheuristik versagen und den Korrektheitsbeweis ungueltig machen.

2. **Statische Transitivitaetsliste (R2-Typ)**: Jede neu als transitiv definierte Relation in pyirk
   muss manuell (oder per Code-Generator) in die .rls-Datei uebernommen werden. Vergessene
   Relationen fuehren zu stillen Korrektheitsfehlem -- keine Fehlermeldung, nur fehlende Ableitungen.

3. **Subprozess-Overhead bei kleinen KBs**: Nemo benoetigt ~6-15 ms Startzeit pro Aufruf. Bei sehr
   kleinen Regellaeufen (<20 ms in pyirk) wuerde die Delegation keinen Netto-Speedup bringen.
   Fuer produktive Nutzung sollte Nemo entweder persistent (Daemon-Modus oder Embedded) oder
   batch-artig (alle Regeln in einem Lauf) angebunden werden.

## Empfehlung

Der Hybrid-Pfad ist klar empfehlenswert: 73 % der Regeln koennen an Nemo delegiert werden,
mit Speedup-Faktoren von 16x bis >1000x, bei bestaedigter Korrektheit. Der verbleibende
Python-Callback-Anteil (27 %) bleibt in pyirk und laeuft sequenziell mit den Nemo-Laeufen.

**Pro Hybrid**:
- Korrektheit fuer R1- und R2-Typ bestaetigt
- Massiver Speedup fuer transitive Regeln (dominanter Bottleneck laut h5_profiling)
- Nemo unterstuetzt Fixpunkt-Semantik nativ, kein eigener Fixpunkt-Loop noetig
- Subprozess-Anbindung sofort einsetzbar ohne pyirk-Kernmodifikation

**Contra / Risiken**:
- Drei verbleibende Risiken (s.o.) erfordern Engineering-Aufwand vor Produktiveinsatz
- Scope-Filter-Logik muss praezisiert werden
- Code-Generator fuer is_transitive-Fakten muss gebaut werden

SPIKE-VERDICT: hybrid_empfohlen=ja
