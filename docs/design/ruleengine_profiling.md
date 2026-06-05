# Rule-Engine Profiling – H5

**Datum:** 2026-06-05  
**Branch:** `h5_profiling`

---

## Messaufbau

- Repo: `/home/user/projekte/pyirk-core`
- Python-venv: `/tmp/pyirk-core-venv/bin/python`
- Test: `test_e01__element_type_rule` in `~/projekte/irk-data/ocse/tests/`
- Anzahl Wiederholungen: 3 (Wall-Clock via `perf_counter`), 1 (cProfile)

Befehl:
```
/tmp/pyirk-core-venv/bin/python -m pytest ~/projekte/irk-data/ocse/tests/ \
  -k test_e01__element_type_rule -p no:randomly -x -s
```

Instrumentierung: `# PROF`-Blöcke temporär in `RuleApplicator.apply()` eingebaut, nach
den Messläufen vollständig entfernt (`git checkout src/pyirk/ruleengine.py`).

---

## Aufschlüsselung Wall-Clock

Gesamt-Wall-Clock (Mittelwert über 3 Läufe): **34.56 s**

Hinweis: `re_total` misst die Zeit innerhalb `RuleApplicator.apply()` (inkl. Matching,
**exkl.** Graph-Aufbau). `create_simple_graph()` wird in `__init__()` aufgerufen, also
**vor** `apply()`, und fließt daher als separate Kategorie (c) ein.

| Kategorie | Sekunden | Anteil % |
|-----------|----------|----------|
| (a) Pattern-Matching inkl. networkx VF2 | 29.885 | 86.5 % |
| (b) Übrige Rule-Engine-Logik (apply − matching) | 0.053 | 0.2 % |
| (c) Substrat / Graph-Erstellung (`create_simple_graph`, in `__init__`) | 0.277 | 0.8 % |
| (d) Sonstiges / Test-Setup | 4.341 | 12.6 % |
| **Gesamt** | **34.556** | **~100 %** |

---

## Top-10-Funktionen nach cumtime (cProfile)

cProfile-Gesamtzeit: 93 s (inkl. ca. 3–5× Profiler-Overhead gegenüber unprofiliertem Lauf).
**Absolutzeiten daher nicht aussagekräftig – nur relative %-Werte verwenden.**

| Rang | Funktion / Modul | ncalls | cumtime-Anteil % |
|------|-----------------|--------|------------------|
| 1 | `ruleengine.py:256(apply)` | 1 | 87.8 % |
| 2 | `ruleengine.py:274(_apply)` | 1 | 87.8 % |
| 3 | `ruleengine.py:553(apply_graph_premise)` | 1 | 87.8 % |
| 4 | `ruleengine.py:897(match_subgraph_P)` | 1 | 87.7 % |
| 5 | `networkx/…/isomorphvf2.py:386(subgraph_monomorphisms_iter)` | 1 | 87.7 % |
| 6 | `networkx/…/isomorphvf2.py:296(match)` | 482 736 | 87.7 % |
| 7 | `networkx/…/isomorphvf2.py:622(syntactic_feasibility)` | 5 995 782 | 52.8 % |
| 8 | `networkx/…/vf2userfunc.py:165(semantic_feasibility)` | 1 369 406 | 11.7 % |
| 9 | `networkx/…/isomorphvf2.py:944(__init__)` | 482 737 | 10.6 % |
| 10 | `networkx/…/vf2userfunc.py:39(_semantic_feasibility)` | 1 852 141 | 10.5 % |

---

## Kennzahlen

| Kennzahl | Wert |
|----------|------|
| Anzahl angewandter Regeln | 1 (`I4731["element type rule"]`) |
| Anzahl Matching-Aufrufe (`match_subgraph_P`) | 1 |
| Graph-Knoten | 2 667 |
| Graph-Kanten | 4 537 |
| VF2-Rekursionen (ncalls `match`) | 482 736 |

---

## Plausibilitäts-Querprobe

Grundlage: vollständiger `test_package.py`-Lauf (19 Tests, 45.61 s).

Kumulativer `[PROF]`-Eintrag nach 3 Regelanwendungen:

| Messgröße | Wert | Anteil an 45.61 s |
|-----------|------|-------------------|
| `re_total` (apply) | 33.18 s | ~72.7 % |
| `matching` | 33.13 s | ~72.6 % |
| `graph` | 0.99 s | ~2.2 % |
| Knoten | 2 845 | – |
| Kanten | 5 166 | – |
| `match_calls` | 3 | – |

Der Matching-Anteil bestätigt den Befund aus dem Einzeltest: Pattern-Matching dominiert
die Laufzeit; alle übrigen Kategorien sind vernachlässigbar.

---

## Fazit

Das networkx-VF2-basierte Subgraph-Monomorphismus-Matching dominiert die Laufzeit der
Rule Engine mit über 86 % der Gesamt-Wall-Clock (Kategorien a+b zusammen: 86.7 %).
Alle anderen Kategorien (Graph-Erstellung, sonstiges Test-Setup) sind vernachlässigbar.
Ein Spike zur Beschleunigung des Matchings ist klar empfehlenswert.

---

GATE-VERDICT: matching_anteil=87% -- spike_empfohlen=ja
