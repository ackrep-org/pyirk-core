# H5 Phase 1 — Abschlussbericht: Hybrid-Regelauswertung mit Nemo

> Branch: `h5_phase1` · Stand: 2026-06-06

---

## 1. Kontext & Zielsetzung

Der Spike-Report (`docs/design/h5_spike_report.md`) belegte 2026-06, dass pyirk-Regeln
vom Typ R1 (reine Tripel-Prämisse) und R2 (Transitivitäts-Propagierung) korrekt an die
Nemo-Rust-Datalog-Engine delegiert werden können — mit einem Speedup von 16× (R1) bzw.
>1000× (R2) inkl. Export-/Import-Overhead. Das Profiling-Resultat war eindeutig: 86,5 % der
`test_e01`-Laufzeit stecken im networkx-VF2-Subgraph-Matching (482 736 Rekursionen für
eine einzige Regel). Die Python-Engine selbst ist fast kostenlos; der Matching-Algorithmus
ist der Engpass.

Das Performance-Designdokument (`docs/design/performance.md`, Abschnitt H5) beschreibt die
daraus folgende Entscheidung: **Hybrid-Pfad mit Nemo, Batch-Materialisierung.** RETE-artige
inkrementelle Materialisierung in Python wurde verworfen — bei diesen Neubewertungskosten
ist vollständige Neuberechnung zuverlässiger und einfacher korrekt zu halten.

**Phase-1-Ziele** (aus `performance.md`, Phase-1-Plan):

1. Exporter generalisieren: vollständiger DataStore→EDB-Export inkl. Qualifier-Abbildung.
2. Regel-Übersetzer/Codegenerator: R1-/R2-Typ automatisch nach `.rls`.
3. OCSE-Skalentest: Fixpunktlauf aller delegierbaren Regeln auf der echten OCSE-KB.
4. Integrationsskizze: Delegationspfad in `ruleengine.py` hinter Feature-Flag.

Alle vier Punkte sind umgesetzt. Die vorliegende Arbeit schließt Phase 1 ab.

---

## 2. Architektur nemobridge

Das Paket `src/pyirk/nemobridge/` enthält drei produktive Submodule und ein
Integrations-Shim. Die Public API wird vollständig über `__init__.py` re-exportiert:

```python
from pyirk.nemobridge import (
    export_datastore, export_relation_facts, is_scope_internal,  # exporter
    classify_rules, generate_transitivity_facts, generate_rls,  # translator
    classification_to_json, RuleClassification,
)
```

### A) Exporter (`src/pyirk/nemobridge/exporter.py`)

Der Exporter wandelt den pyirk-`DataStore` in eine **Nemo-kompatible EDB** (Extensional
Database) aus CSV-Dateien um.

**Ausgabe-Konvention** — drei Kategorien:

| Datei | Inhalt | Spalten |
|---|---|---|
| `triples.csv` | Alle unqualifizierten Statements | `(subject_key, predicate_key, object_key)` |
| `stmts.csv` | Statements mit mindestens einem Qualifier | `(stmt_id, subject_key, predicate_key, object_key)` |
| `quals_<rel_key>.csv` | Je eine Datei pro Qualifier-Relation | `(stmt_id, value)` |

Statements, deren Objekt ein Literal (kein Item/Relation) ist, werden aus `triples.csv`
herausgefiltert, da Nemo nur ground-term-Fakten unterstützt.

**Qualifier-Reifikation:** Statt qualifizierte Aussagen als n-äre Prädikate mit fester
Spaltenanzahl zu kodieren, verwendet der Exporter eine Reifikationsstrategie mit separaten
`quals_*.csv`-Dateien je Qualifier-Relation. Begründung: (a) Statements können
unterschiedliche Teilmengen von Qualifiern haben — ein festes n-äres Prädikat erforderte
viele NULL-Spalten oder separate Regeln; (b) Nemo unterstützt heterogene Fakttabellen gut;
(c) Phase-2-Join-Regeln können `stmts.csv` mit `quals_*.csv` direkt verbinden.

**Scope-interner Filter (`is_scope_internal`):** Entitäten mit mindestens einer
`R20__has_defining_scope`-Relation sind Platzhalter/Pattern-Variablen aus der pyirk-Regel-
Konditionserfassung. Sie werden beim Export ausgeschlossen, da sie keine realen Fakten
repräsentieren.

**OCSE-Zahlen (P3):** 1919 unqualifizierte Tripel + 59 qualifizierte Statements im
vollständigen OCSE-Export.

### B) Translator (`src/pyirk/nemobridge/translator.py`)

Der Translator analysiert alle `I41__semantic_rule`-Instanzen im DataStore und erzeugt
automatisch Nemo-`.rls`-Regelcode.

**Regelklassifikation (`classify_rules`)** → Dataklasse `RuleClassification`:

| Kategorie | Bedeutung | Codegen |
|---|---|---|
| `direct` | Reine Tripel-Prämisse, nach Datalog übersetzbar | RLS-Snippet direkt aus Prämisse/Konklusion |
| `transitive` | R2-Typ: `R60__is_transitive`-Marker + Wildcard-Relation | Standard-trans/3-Muster via `generate_transitivity_facts()` |
| `python_only` | Python-Callback, SPARQL, OR-Subscope o.ä. | Kein Codegen — verbleibt in Python-Engine |

**Generiertes `.rls`-Muster:**

```
@import triples :- csv{resource="triples.csv"} .

% Direct rules — Beispiel I64
R83(?i2, ?i1) :- triples(?i2, R3, ?i1) .

% Transitive closure — Standard-Datalog für R2-Typ
is_transitive(R17) .
trans(?s, ?p, ?o) :- triples(?s, ?p, ?o), is_transitive(?p) .
trans(?i1, ?r, ?i3) :- is_transitive(?r), trans(?i1, ?r, ?i2), trans(?i2, ?r, ?i3) .

@export R83 :- csv{resource="output_R83.csv"} .
```

Da Nemo alle Regeln im gemeinsamen Fixpunkt auswertet, berechnen I64 und I65 zusammen
automatisch die transitive Hülle von R83.

---

## 3. P3 — OCSE-Skalentest

### Korrektheit

| Kennzahl | Wert |
|---|---|
| pyirk-Tupel (gesamt) | **373** |
| Nemo-Tupel (gesamt) | **373** |
| Identisch? | **JA** |
| Diff | keiner |

**Tupelaufschlüsselung nach Regel:**

| Relation | Regeln | Tupel |
|---|---|---|
| R83 | I64/I65 (generalized subclass) | 299 |
| R17 | I66 (transitiv) | 74 |
| R30 | I4731 (element type) | 0 neue |

R30 erzeugt auf den OCSE-Daten keine neuen Fakten (alle R30-Statements bereits vor der
Regelanwendung vorhanden).

### Timing

Messung: best-of-2 Läufe, unter erhöhter Systemlast (load=1.01–1.27).

**pyirk misst:** `apply_semantic_rules(*delegatable_rules, exhaust=True)`
**Nemo misst:** `export_datastore + generate_rls + nmo-Run + Output-Parse`

| Run | pyirk (s) | Nemo (s) |
|-----|-----------|----------|
| 1 | 348.1167 | 0.4685 |
| 2 | 348.1978 | 0.4470 |
| **Best** | **348.12** | **0.447** |

**Speedup: 779x (load-belastet, load=1.01–1.27)**

Hinweis: Nemo-Zeiten sind durch Systemlast kaum beeinflussbar (CPU-satt-gebunden intern).
Der Speedup ist bei 779× robust. Eine Wiederholung auf unbelastetem VPS (Phase 2) könnte
die pyirk-Seite etwas günstiger zeigen.

#### Nachtrag (2026-06-07): saubere Wiederholung auf ruhigem VPS

best-of-5, VPS bei Start nachweislich ruhig (loadavg 0.01, einziger Fremdprozess node/openclaw
@1.2 %). pyirk best **362.84 s**, Nemo best **0.4569 s** → **Speedup 794×** — bestätigt den
779×-Wert (kein Last-Artefakt). Die Per-Run-Lastwarnung des Skripts (`load=1.27`, Prozess @99.9 %)
ist ein **Fehlalarm**: es ist pyirks *eigener* Mess-Subprozess, nicht Fremdlast. Das automatische
`(load-belastet)`-Label in der Verdict-Zeile ist daher in beiden Läufen self-induced und kann
ignoriert werden; die Messumgebung war sauber. Belastbarer Kennwert: **~790× (362.8 s → 0.457 s)**.

---

## 4. Regel-Klassifikation OCSE

Aus `experiments/h5_phase1/p3_rule_classification.json` (4 Regeln gesamt):

| Key | Label | Kategorie |
|-----|-------|-----------|
| I64 | introduction of generalized subclass statements | direct |
| I65 | propagation of generalized subclass | direct |
| I66 | propagation transitive relations | transitive |
| I4731 | element type rule | direct |

**Zähler je Kategorie:** `direct=3, transitive=1`

Delegierbare Regelkopf-Prädikate: R30, R83 (direct); R17 (transitive).

---

## 5. P4 — Integrationsskizze

### Feature-Flag

```bash
PYIRK_NEMO_DELEGATION=1 python ...
```

Ohne dieses Flag: unverändertes Python-Verhalten — kein Nemo-Aufruf, keine Laufzeit-
Abhängigkeit vom Binary.

### Hook-Stelle

`src/pyirk/ruleengine.py:77` — Beginn des Nemo-Delegationsblocks in `apply_semantic_rules()`.

```python
if os.environ.get("PYIRK_NEMO_DELEGATION"):
    from pyirk.nemobridge.delegation import (
        _nemo_available, _split_rules_by_nemo_delegation, _apply_via_nemo,
    )
    if _nemo_available():
        try:
            delegated, remaining = _split_rules_by_nemo_delegation(rules)
            if delegated:
                _apply_via_nemo(delegated, mod_context_uri)
                rules = tuple(remaining)
        except Exception as ex:
            logger.warning("Nemo delegation failed, falling back to Python: %s", ex)
```

### Stiller Fallback

Greift automatisch bei:
- fehlendem Nemo-Binary (Standardpfad `/home/user/bin/nmo`, überschreibbar via `PYIRK_NEMO_BIN`)
- jeder Exception aus dem Delegationspfad (einschließlich Phase-1-`NotImplementedError`)

Kein Log-Spam bei fehlendem Binary; `logger.warning` nur bei unerwarteter Exception.

### Ausführungsreihenfolge (bei aktivem Flag)

1. **Nemo-Block**: delegierbare Regeln (Kategorie `direct` + `transitive`) → Nemo bis Fixpunkt
2. **Python-Block**: restliche Regeln (`python_only`, SPARQL, OR-Subscope) → Python-Engine

### Bekannte Limitation Phase 1

`_apply_via_nemo()` führt die Pipeline vollständig aus (Export → RLS-Codegen → `nmo`-Aufruf),
bricht aber **vor** dem CSV→Statement-Mapping mit `NotImplementedError` ab. Der stille Fallback
greift daher in Phase 1 immer. Der Hook ist primär Skelett und Codepfad-Validierung — der
Nemo-Lauf selbst wird ausgeführt, aber seine Ergebnisse noch nicht zurückgeschrieben.

Begründung für Phase-2-Verschiebung des Mappings: pyirk-Item-Auflösung aus Short-Keys
erfordert Live-DataStore-Zugriff, Qualifier-Reifikation muss rückgebaut werden, und
Duplikat-Prüfung gegen bereits existierende Statements ist notwendig.

---

## 6. Offene Punkte für Phase 2

- **CSV → `core.Statement`-Mapping** inkl. Qualifier-Reifikation und Duplikat-Prüfung —
  Kernaufgabe, die Phase 1 bewusst ausspart.
- **Rückkopplung Nemo-Block ↔ Python-Block**: `python_only`-Ergebnisse, die delegierbare
  Regeln erneut triggern würden, sind in Phase 1 ignoriert.
- **Weitere Regelkategorien prüfen**: SPARQL-Regeln, OR-Subscope — könnten teilweise
  ebenfalls delegierbar sein.
- **Daemon-Modus**: Bei vielen kleinen Läufen (interaktive Sessions) könnte ein
  persistenter Nemo-Prozess den Subprozess-Startoverhead eliminieren.
- **Saubere Timing-Wiederholung** auf unbelastetem VPS — P3 lief unter last=1.01–1.27;
  Nemo-Zahlen sind robust, pyirk-Zahlen könnten leicht besser sein.

---

PHASE1-VERDICT: ocse_korrekt=ja speedup_test_e01=779x (load-belastet)
