# Designdokument: LLM-gestütztes Authoring für pyirk via MCP

Status: Entwurf (early alpha-Kontext). Zielgruppe: Autor (Carsten Knoll) als Solo-Entwickler.
Dieses Dokument beschreibt **kein Code**, sondern eine Architektur. Prosa Deutsch,
technische Identifier (`create_item`, `R4`, MCP-Tools etc.) im Original.

---

## 1. Motivation & Ziele

pyirk repräsentiert Wissen als imperativen Python-Code: Items (`I1234`) und Relationen
(`R1234`) mit sprechenden Label-Suffixen, erstellt über `p.create_item(...)` /
`p.create_relation(...)` (siehe `src/pyirk/core.py:1459` bzw. `:1835`). Ein Modul ist eine
`.py`-Datei mit `__URI__`, `p.register_mod(...)`, `p.start_mod(...)`, gefolgt von vielen
`create_item`-Aufrufen, abgeschlossen durch `p.end_mod()` (vgl.
`tests/test_data/zebra_base_data.py`).

**Annahme A1 (Solo / knappe Zeit):** Es stehen keine Studierenden zur Verfügung. Der Autor
arbeitet allein mit knapper Zeit. Jede Lösung muss daher den **menschlichen Aufwand pro
modelliertem Fakt** minimieren, nicht primär den Maschinendurchsatz.

**Nordstern-Use-Case (Mathebuch):** Es existiert der **LaTeX-Quelltext eines Mathebuchs**,
der erst zu einem kleinen Teil in pyirk-Code überführt ist. Ziel ist langfristig eine
**agentische Lösung**, die diese Überführung fortsetzt. Das ist Zukunftsmusik; der enablende
**erste Schritt ist ein MCP-Server**, der pyirks lebenden `DataStore` (`ds`,
`src/pyirk/core.py:787`) einem LLM als Werkzeuge exponiert.

**Beobachtung (die drei echten Engpässe):** Nicht die Syntax ist das Problem (Python können
LLMs gut), sondern:

1. **Wiederverwendung statt Duplikat** — das größte Versagensmuster ist, dass das LLM
   Entitäten halluziniert oder dupliziert, die längst existieren (z. B. ein zweites
   `I.... "human"` neben `I7435`).
2. **Modellierungsentscheidungen** — Subklasse (`R3__is_subclass_of`) vs. Instanz
   (`R4__is_instance_of`) vs. sekundäre Instanz (`R30__is_secondary_instance_of`); neues Item
   vs. vorhandenes wiederverwenden; Metaclass (`p.I2["Metaclass"]`) vs. normale Klasse.
3. **Grounding** — ohne sofortige Validierung produziert das LLM "plausibel, aber falsch".

**Ziele:**

- G1: Vor jeder Neuanlage zuverlässige **Retrieval-first**-Suche über vorhandene Entitäten.
- G2: **Modellierungs-Gabelungen** explizit machen (2–3 Alternativen mit Trade-offs, Mensch
  wählt).
- G3: **Sofort-Validierung** (consistency_checking, R8–R11-Range-Checks, Rule-Engine) mit
  Rückkanal der Fehler ans LLM.
- G4: Ausgabe ist **deterministischer, diff-barer** pyirk-`.py`-Code, der unverändert per
  `irkloader` ladbar bleibt.

---

## 2. Non-Goals / Scope

- **MCP-first:** Gegenstand dieser Phase ist ausschließlich der MCP-Server plus
  Tool-Oberfläche und das Human-in-the-loop-Interaktionsmodell.
- **Keine** vollautomatische End-to-End-Textbuch-Pipeline in dieser Phase. LaTeX-Extraktion
  und autonome Multi-Agent-Läufe sind spätere Phasen (Abschnitt 8 / 10).
- **Keine** Änderung des pyirk-Kerns als Voraussetzung: Der Server nutzt die öffentliche API
  (`import pyirk as p`) und ausgewählte interne Strukturen (`p.ds`, `ruleengine`,
  `consistency_checking`) read-mostly. Kernänderungen werden als optionale Hooks markiert.
- **Kein** eigenes Persistenz-/DB-Format: Single Source of Truth bleiben die Modul-`.py`-
  Dateien.
- **Keine** GUI in dieser Phase; Interaktion läuft über den MCP-Client (der Chat-Agent) und
  Approval-Prompts.

---

## 3. MCP-Tool-Oberfläche

Grundprinzip: Der Server hält genau eine pyirk-Session (geladener `DataStore`) plus genau ein
**Ziel-Modul** ("Working Module"), an das neue Entitäten angehängt werden. Tools zerfallen in
**Read/Query**, **Propose/Validate** (wirken nur auf einen Staging-Puffer, nicht auf Dateien)
und **Commit** (schreibt Datei).

### 3.1 Read / Query

- `load_session(module_uris: list[str], working_module: str) -> SessionInfo`
  Lädt eine Menge bestehender Module per `irkloader.load_mod_from_uri` (vgl.
  `src/pyirk/irkloader.py:41`) und setzt das Working Module. Begründung: Der Agent muss den
  **vollständigen vorhandenen Kontext** sehen, bevor er etwas anlegt (G1). Liefert Anzahl
  Items/Relationen und die geladenen URIs zurück.

- `search_entities(query: str, top_k: int = 10, etype: "item"|"relation"|"any" = "any") -> list[Hit]`
  **Semantische + lexikalische** Suche über `R1__has_label` und `R2__has_description` aller
  Entitäten in `ds.items` / `ds.relations`, angereichert um `R33__has_corresponding_wikidata_entity`
  (siehe Abschnitt 5). Jeder `Hit` enthält `uri`, `short_key`, `R1`, `R2`, Klassenzugehörigkeit
  (`R4`/`R3`), Wikidata-Link und Score. Begründung: Kerninstrument gegen Duplikate (G1). Dieses
  Tool MUSS laut Server-Policy vor jedem `propose_create_item` aufgerufen werden.

- `get_entity(uri_or_key: str) -> EntityDetail`
  Volle Entität: alle ausgehenden Statements (via `Entity.get_relations`,
  `src/pyirk/core.py:584`) und inverse Statements (`get_inv_relations`), Label, Beschreibung,
  Usage-Hints (`R18`), Domains (`R8`/`R9`/`R10`), Range (`R11`), Wikidata (`R33`). Begründung:
  Wiederverwendungs-Entscheidung braucht den exakten Ist-Zustand eines Kandidaten.

- `get_taxonomy(uri_or_key: str, direction: "up"|"down"|"both" = "both", depth: int = 3) -> TaxonomyTree`
  Liefert die Klassenhierarchie um eine Entität: nach oben via `R3`/`R4`
  (`get_taxonomy_tree`, `src/pyirk/_builtin/taxonomy.py:97`), nach unten via
  inverser `R4`-Suche (`get_direct_instances_of`, `:294`) und inverser `R3`. Begründung:
  Modellierungsentscheidung Subklasse-vs-Instanz braucht den Blick auf die umgebende
  Taxonomie.

- `query_sparql(sparql: str) -> Table`
  Dünner Wrapper um `rdfstack.perform_sparql_query` (`src/pyirk/rdfstack.py:172`). Begründung:
  Für strukturelle Fragen ("alle Instanzen von X mit Eigenschaft Y") ist SPARQL präziser als
  Volltextsuche. Optionales Tool; Score-getriebene Suche bleibt der Default.

### 3.2 Propose / Validate (Staging, keine Dateischreibung)

Diese Tools wirken auf einen **In-Memory-Staging-Puffer** (Abschnitt 4). Sie führen die
pyirk-Operation real im `DataStore` aus (damit Validierung greift), markieren die erzeugten
Entitäten aber als "staged" und reversibel.

- `propose_modeling(intent: str, retrieval_hits: list[uri]) -> list[ModelingOption]`
  Der Agent beschreibt die Modellierungsabsicht in natürlicher Sprache; das Tool gibt
  **2–3 strukturierte Alternativen** zurück, jede mit: gewählter Relation
  (`R3` vs `R4` vs `R30`), Eltern-Item, Begründung und Trade-offs. Begründung: macht die
  Gabelung explizit und maschinenlesbar (G2); ist der Aufhänger für Human-in-the-loop
  (Abschnitt 6). Die Optionen können regelbasiert vorgeschlagen werden (z. B. "Ziel ist eine
  benennbare Einzelentität → `R4`-Instanz von gefundener Klasse" vs. "Ziel ist eine
  Verallgemeinerung → `R3`-Subklasse").

- `propose_create_item(R1: str, R2: str, parent: uri, mode: "R3"|"R4"|"R30", extra: dict, wikidata: str|None) -> StagedEntity`
  Legt ein Item **im Staging** an: ruft intern `p.create_item(R1__has_label=..., R2__has_description=...)`
  und setzt `R3`/`R4`/`R30` gemäß `mode`, plus `R33` falls `wikidata` gesetzt. `extra` erlaubt
  weitere Relationen (`R8`–`R11`, `R5`, ...). Begründung: gezielte, geprüfte Einzelanlage statt
  freie Code-Generierung; verhindert dass das LLM Syntax/Bootstrapping fummelt.

- `propose_create_relation(R1: str, R2: str, R8: uri|None, R11: uri|None, functional: bool) -> StagedEntity`
  Analog für `p.create_relation`; `R8__has_domain_of_argument_1`, `R11__has_range_of_result`,
  `R22__is_functional`. Begründung: neue Relationen sind seltener und riskanter (Domain/Range);
  eigenes Tool erlaubt strengere Prüfung.

- `propose_statement(subject: uri, predicate: uri, object: uri|literal, qualifiers: list|None) -> StagedStatement`
  Fügt ein Statement an eine (vorhandene oder gestagte) Entität an, entspricht
  `entity.set_relation(...)`. Begründung: Wiederverwendung bestehender Items durch *Verlinken*
  statt Neuanlage ist der direkteste Hebel gegen Duplikate (G1).

- `validate(scope: "staged"|"working_module"|"all" = "staged") -> ValidationReport`
  Führt die in Abschnitt 7 beschriebenen Checks aus und liefert strukturierte Fehler
  (Typ, betroffene `uri`, Message) zurück. Begründung: Grounding (G3); der Rückkanal, mit dem
  das LLM aus Fehlern lernt, bevor etwas committet wird.

- `discard_staged(uri_or_all) -> None`
  Verwirft gestagte Entitäten/Statements und entfernt sie sauber aus dem `DataStore`
  (analog `p.unload_mod`-Mechanik auf Eintragsebene). Begründung: ein fehlgeschlagener
  Vorschlag darf den lebenden Zustand nicht vergiften.

### 3.3 Commit

- `commit_to_module(path: str|None = None, dry_run: bool = True) -> Diff`
  Serialisiert alle gestagten Entitäten/Statements als **deterministischen pyirk-`.py`-Code**
  und hängt sie an die Datei des Working Module an (oder erzeugt sie). `dry_run=True` liefert
  nur den Unified-Diff. Begründung: G4 — menschlich reviewbar, versionierbar, und das Ergebnis
  ist wieder ladbar via `irkloader`. Der Commit ist die einzige Operation, die das Dateisystem
  verändert.

**Tool-Policy (Server-seitig erzwungen):** `propose_create_item` ohne vorausgegangenes
`search_entities` mit überlappendem Query wird abgelehnt bzw. mit Warnung versehen. Das ist
der mechanische Kern von "Retrieval-first".

---

## 4. Architektur

```
   LLM/Chat-Agent  <—MCP(stdio/json-rpc)—>  pyirk-MCP-Server (Python-Prozess)
                                              |
                                              |— import pyirk as p   (eine Session)
                                              |— p.ds : DataStore (lebender Zustand)
                                              |— irkloader.load_mod_from_uri(...)
                                              |— ruleengine / consistency_checking
                                              |— Staging-Puffer (StagedEntity[])
                                              |— Serializer -> module.py  (Diff/Write)
```

- **Andocken an den DataStore:** Der Server importiert pyirk einmalig und hält die Session.
  `load_session` lädt Basismodule via `irkloader.load_mod_from_uri` (`src/pyirk/irkloader.py:41`),
  was `ds.items`, `ds.relations`, `ds.statements` füllt. Alle Read-Tools lesen direkt aus `ds`.

- **Lebender Zustand zwischen Aufrufen:** Der Serverprozess bleibt am Leben; `ds` ist global
  (Modulvariable in `core`). MCP-Aufrufe sind daher zustandsbehaftet bzgl. dieser Session.
  **Annahme A2:** Single-Session pro Serverprozess; keine Nebenläufigkeit mehrerer Agenten auf
  demselben `ds` (mehr dazu in Risiken).

- **Staging-Modell:** `propose_*`-Tools setzen das **Working Module** als aktives Modul
  (`p.start_mod(working_uri)` / `p.end_mod()` paarweise um jeden Aufruf, oder ein offenes
  "Authoring-Modul" über die Session) und tracken die erzeugten `uri`s über
  `ds.entities_created_in_mod[working_uri]` (`src/pyirk/core.py:797`) sowie
  `ds.stms_created_in_mod`. Damit ist exakt bekannt, was in dieser Session neu ist — die Basis
  für `discard_staged`, `validate(scope="staged")` und `commit_to_module`.

- **Deterministische Serialisierung (diff-bar):** Der Serializer rendert je gestagter Entität
  einen kanonischen `create_item(...)`-Block im Stil von `zebra_base_data.py`:
  - feste Reihenfolge der kwargs (`R1`, `R2`, `R4`/`R3`/`R30`, `R33`, dann Rest sortiert nach
    Key),
  - Referenzen auf vorhandene Items als `pX["label"]` (Prefix des Quellmoduls) bzw.
    `IXXXX["label"]` für Items im selben Modul,
  - stabile Variablennamen (`IXXXX = p.create_item(...)`),
  - keine Zeitstempel/Zufall im generierten Code.
  Append-only an die Working-Module-Datei (vor `p.end_mod()`), damit Diffs minimal bleiben.
  **Offene Frage F1:** Schlüsselvergabe — feste Keys (reproduzierbar, aber Kollisionsrisiko)
  vs. `KeyManager`-Seed (vgl. `keyseed=1835` in `zebra_base_data.py`). Vorschlag: Keys beim
  Commit aus dem `KeyManager` des Working Module ziehen und in den generierten Code einbacken.

- **Round-Trip-Garantie:** Nach Commit wird das Working Module testweise neu geladen
  (`irkloader` mit `reuse_loaded=False`), um sicherzustellen, dass der generierte Code lädt und
  die Validierung weiterhin grün ist. Schlägt das fehl, wird der Commit als fehlerhaft
  gemeldet (Datei bleibt, aber Report markiert Regression).

---

## 5. Retrieval / Embedding-Ansatz

Ziel: Duplikate verhindern, indem **vor** jeder Neuanlage semantisch ähnliche Bestände
sichtbar werden (G1).

- **Korpus:** Für jede Entität in `ds.items` und `ds.relations` ein Dokument aus
  `R1__has_label` + `R2__has_description` (+ optional `R18__has_usage_hint`). `R33`-Wikidata-
  Links dienen als zusätzliches, hochpräzises Matching-Signal.
- **Index (zwei Lagen):**
  1. **Lexikalisch** (sofort, kein Modell): normalisierte Substring-/Token-Suche über Labels —
     fängt exakte und Beinahe-Duplikate ("human" vs "human being").
  2. **Embedding** (semantisch): Label+Description-Vektoren in einem lokalen Vektorindex.
     **Annahme A3:** lokales Embedding-Modell (z. B. via `sentence-transformers`) ist
     akzeptabel; falls nicht verfügbar → reine lexikalische + Wikidata-Suche als Fallback.
- **Wikidata-Brücke:** Wenn der Intent ein Wikidata-Konzept benennt (oder der Agent eine
  Q-/P-Nummer kennt), wird zuerst über `R33` exakt gematcht. Treffer dort sind die stärksten
  Duplikat-Indikatoren, weil `R33` semantische Identität über die Sprachebene hinaus kodiert.
- **Index-Aktualität:** Der Index wird bei `load_session` aufgebaut und bei jedem erfolgreichen
  `propose_create_item` inkrementell ergänzt, damit auch innerhalb einer Session keine
  Selbst-Duplikate entstehen.
- **Anti-Duplikat-Mechanik:**
  - `search_entities` liefert Score + Begründung; bei Score über Schwelle markiert der Server
    den Treffer als "likely duplicate".
  - `propose_create_item` mit hohem Duplikat-Score wird zu einer **Gabelung** eskaliert
    ("vorhandenes `I7435 human` wiederverwenden?" vs. "wirklich neu, weil ...").
  - Server-Policy (Abschnitt 3.3): keine Neuanlage ohne vorausgegangene Suche.

---

## 6. Human-in-the-loop-Interaktionsmodell

Leitidee: Der Mensch entscheidet **Gabelungen**, nicht jede Zeile. Drei Eskalationsstufen:

1. **Auto (kein Prompt):** eindeutige Fälle — Suche ergibt klaren Treffer und der Agent
   *verlinkt* (`propose_statement`) statt neu anzulegen; oder Neuanlage ohne Duplikat-Verdacht
   und mit eindeutiger Modellierung (z. B. weitere Instanz einer bereits etablierten Klasse wie
   `I7435["human"]`).
2. **Gabelung (Auswahl-Prompt):** `propose_modeling` liefert 2–3 `ModelingOption`s; der MCP-
   Client präsentiert sie dem Menschen als knappe, referenzierbare Auswahl:
   ```
   F: Wie "Stetigkeit" modellieren?
     (a) R4-Instanz von I.... "mathematical property"  — einfach, passt zu vorhandenen Properties
     (b) R3-Subklasse von I.... "property"             — falls Unterarten (gleichmäßig/lokal) folgen sollen
     (c) Wiederverwenden: I.... existiert bereits        — vermeidet Duplikat
   ```
   Die Auswahl (a)/(b)/(c) wird zurück an `propose_create_item` gereicht.
3. **Review (Diff-Approval):** `commit_to_module(dry_run=True)` zeigt den Unified-Diff; der
   Mensch approved → realer Write. Das ist das letzte Gate vor Dateisystemänderung.

**Designentscheidung:** Gabelungen werden als strukturierte Optionen (Daten), nicht als
Freitext geführt, damit sie protokollier- und später (Phase 3) batch-entscheidbar sind
(z. B. "immer (a) für mathematische Eigenschaften"). Wiederkehrende Entscheidungen können als
**Modellierungs-Policy** gespeichert werden, um die Prompt-Last bei knapper Zeit (A1) zu
senken.

---

## 7. Validierungs-Integration

Die Checks existieren bereits im Code und werden über Tools/Hooks angezapft:

- **Item-Finalisierung (Hook):** `consistency_checking.enable_consistency_checking()`
  registriert `check` als `post-finalize-item`-Hook (`src/pyirk/consistency_checking.py:197`).
  `check` validiert u. a. angewandte Operatoren (`check_applied_operator`) inklusive
  **Argument-Typprüfung** gegen erwartete Domains. Der MCP-Server aktiviert diesen Hook in der
  Session; Verstöße erscheinen als `IrkTypeError`/`WrongArgType`/`WrongArgNumber` und werden in
  `validate()` als strukturierte Fehler weitergereicht.
- **R8–R11-Range-Checks:** `get_expected_arg_types` (`:153`) plus `check_type` (`:93`) prüfen,
  ob die Argumente einer Mapping-Anwendung zur deklarierten Domain (`R8`/`R9`/`R10`) bzw. Range
  (`R11`) passen, inkl. `R3`-Subklassen und `R30`-Sekundärtypen (`is_subclass_of`,
  `src/pyirk/_builtin/taxonomy.py:134`). Genau dieser Pfad fängt die häufigen
  Modellierungsfehler des LLM.
- **Rule-Engine-Lauf:** `validate()` ruft optional `ruleengine.apply_all_semantic_rules()`
  (`src/pyirk/ruleengine.py:42`) bzw. gezielt `apply_semantic_rules(..., exhaust=True)` auf und
  meldet `ConstraintViolation`-artige Resultate. So werden modul-eigene Konsistenzregeln
  (I41-`semantic rule`) genutzt, statt sie nachzubauen.
- **Lade-Validierung:** Beim Commit der finale Round-Trip-Reload via `irkloader` (Abschnitt 4).

**Wann läuft was:**

| Zeitpunkt                | Check                                                        |
|--------------------------|-------------------------------------------------------------|
| nach jedem `propose_*`   | Finalize-Hook (`check`) auf die neue Entität                |
| explizit via `validate`  | Hook-Replay + R8–R11 + Rule-Engine über `staged`/`module`   |
| bei `commit_to_module`   | Round-Trip-Reload + `validate(scope="working_module")`      |

**Rückkanal:** Jeder Fehler wird als `{type, uri, message, hint}` an das LLM zurückgegeben.
`message`/`hint` stammen aus den realen Exceptions (z. B. "expected one of [...] but got [...],
while checking type of arg1 for ..."), womit das LLM gezielt korrigieren kann, statt zu raten.

---

## 8. LaTeX-Mathebuch-Pipeline (Zukunft, grob skizziert)

Setzt **auf** die MCP-Tools auf; fügt nur eine Extraktions- und Orchestrierungsschicht hinzu:

1. **Segmentierung:** LaTeX-Quelle in Einheiten (Definition, Satz, Bemerkung, Beispiel)
   zerlegen; Mathe-Ausdrücke (`R24__has_LaTeX_string`) erhalten.
2. **Extraktion → Intent:** Pro Segment formuliert ein Extraktions-Agent strukturierte
   Modellierungsabsichten (Konzept, Typ, Beziehungen) — noch keine pyirk-Statements.
3. **Retrieval & Modellierungsvorschläge:** Für jede Absicht `search_entities` +
   `propose_modeling` (Wiederverwendung vor Neuanlage).
4. **Validierung:** `validate(scope="staged")` nach jedem Segment; Fehler zurück an den Agenten
   (gleicher Rückkanal wie Abschnitt 7).
5. **Human-in-the-loop / Policy:** Gabelungen werden gegen gespeicherte Modellierungs-Policy
   (Abschnitt 6) automatisch aufgelöst, sonst an den Menschen eskaliert — Batch-Review statt
   Einzel-Prompt, passend zu A1.
6. **Commit:** `commit_to_module` pro Kapitel/Abschnitt → ein diff-barer pyirk-Code-Block.

Der LaTeX-spezifische Teil ist damit dünn; die Korrektheit kommt aus den MCP-Tools.

---

## 9. Risiken & offene Fragen

- **R-A: Globaler Zustand / Nebenläufigkeit.** `ds` ist prozessglobal; mehrere parallele
  Agenten oder Sessions können sich gegenseitig korrumpieren (A2). Mitigation: ein
  Serverprozess pro Session; spätere Multi-Agent-Läufe (Phase 3) brauchen entweder
  Prozess-Isolation oder Snapshot/Restore von `ds`.
- **R-B: Reversibilität von Staging.** `discard_staged` muss Items *und* die von ihnen
  ausgelösten Statements/Hook-Effekte sauber entfernen. `unload_mod` arbeitet modulweise; eine
  feinkörnige Einzel-Entfernung ist zu verifizieren. **Offene Frage F2:** reicht
  Working-Module-weites Unload + Replay, oder ist Einzel-Rollback nötig?
- **R-C: Schlüsselvergabe / Reproduzierbarkeit** (F1, Abschnitt 4).
- **R-D: Embedding-Verfügbarkeit/Qualität** (A3). Fallback definiert, aber Duplikat-Recall
  sinkt ohne semantische Vektoren.
- **R-E: Validierungs-Abdeckung.** `consistency_checking.check` deckt aktuell v. a. angewandte
  Operatoren ab; viele andere Itemarten haben "no checks implemented yet" (`:38`). Falsche
  Sicherheit möglich. Mitigation: Rule-Engine + Round-Trip-Reload als zusätzliche Netze.
- **R-F: Über-Eskalation.** Zu viele Gabelungs-Prompts erschöpfen die knappe Zeit (A1).
  Mitigation: Policy-Speicher, Auto-Stufe für eindeutige Fälle.
- **Offene Frage F3:** MCP-Transport (stdio vs. HTTP) und Einbettung in den bevorzugten
  Client.
- **Offene Frage F4:** Soll `commit_to_module` immer append-only sein, oder auch bestehende
  Blöcke umschreiben dürfen (Refactoring)? Append-only ist sicherer und diff-freundlicher.

---

## 10. Phasenplan

Die Phasen sind so geschnitten, dass jede spätere Phase als `goal.md` einen autonomen
(Multi-Agent-)Lauf treiben kann.

- **Phase 0 — Skelett & Read-Only.** MCP-Server-Gerüst; `load_session`, `search_entities`
  (nur lexikalisch + `R33`), `get_entity`, `get_taxonomy`. Erfolgskriterium: Agent kann den
  vorhandenen Bestand korrekt referenzieren, legt nichts an.
- **Phase 1 — Staging & Validierung.** `propose_create_item/relation`, `propose_statement`,
  `validate` (Finalize-Hook + R8–R11 + Rule-Engine), `discard_staged`. Erfolgskriterium:
  Agent legt geprüfte Einzelentitäten an, fehlerhafte Vorschläge werden mit verwertbarem
  Rückkanal abgelehnt; nichts wird in Dateien geschrieben.
- **Phase 2 — Commit & Round-Trip.** Deterministischer Serializer, `commit_to_module`
  (dry_run-Diff + Write), Round-Trip-Reload. Erfolgskriterium: generierter Code lädt via
  `irkloader` und bleibt validierungsgrün; minimale, reviewbare Diffs.
- **Phase 3 — Retrieval-Ausbau & Policy.** Embedding-Index, Duplikat-Eskalation,
  `propose_modeling`, Modellierungs-Policy-Speicher. Erfolgskriterium: messbar weniger
  Duplikate und weniger Human-Prompts pro Fakt.
- **Phase 4 — LaTeX-Pipeline (autonomer Lauf).** Extraktions-Agent + Orchestrierung über die
  MCP-Tools (Abschnitt 8); dieser Phasenabschnitt ist als `goal.md`-Kandidat für einen
  Multi-Agent-Lauf gedacht. Erfolgskriterium: ein Kapitel des Mathebuchs wird halbautonom in
  validen, gemergten pyirk-Code überführt, mit Batch-Review der offenen Gabelungen.

---

*Annahmen-Übersicht:* A1 (Solo/knappe Zeit), A2 (Single-Session pro Prozess),
A3 (lokales Embedding optional, mit Fallback). Offene Entscheidungen: F1 (Keyvergabe),
F2 (Staging-Rollback-Granularität), F3 (MCP-Transport), F4 (append-only vs. Rewrite).
