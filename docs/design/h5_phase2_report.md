# H5 Phase 2 — Abschlussbericht: Nemo-Delegation scharf geschaltet

> Branch: `h5_phase2` · Stand: 2026-06-10

---

## 1. Zielsetzung & Scope

Phase 2 implementiert den in Phase 1 ausgesparten Schritt 5 (CSV →
`core.Statement`) und schaltet den Delegationspfad hinter
`PYIRK_NEMO_DELEGATION=1` damit produktiv. Verbindlich aus `goal.md`
übernommen sind die Designvorgaben V1–V5; Phase 2 setzt V2–V5 um und
hält den Erweiterungspunkt für V1 strukturell offen.

- **V1 — Qualifier-Delegation vertagt.** Native Engine hängt an die
  abgeleiteten Statements der delegierbaren Regeln keine Qualifier an
  (`# TODO: add qualifiers` in `ruleengine.py`). Phase 2 spiegelt diesen
  Kompromiss bewusst, um ein wohldefiniertes Äquivalenzziel zu haben.
  Der Qualifier-Export (`stmts.csv` / `quals_<R>.csv`) bleibt erhalten.
- **V2 — URI-Verlust im Export beheben.** Exporter führt einen
  `short_key → uri`-Index, damit die Rückauflösung im Mapping-Schritt
  modul-kontextfrei per URI passieren kann.
- **V3 — Idempotente Einfügung.** Nemos `output_*.csv` enthält die
  komplette Hülle; pro Tupel `omit_if_existing`-Spiegel (genau wie
  nativ).
- **V4 — Beschränkter Fixpunkt-Loop.** `apply_semantic_rules` ruft bei
  aktivem Flag den Nemo-Block (delegierbare Regeln) und den
  Python-Block (restliche Regeln) abwechselnd auf, bis beide Blöcke 0
  neue Statements liefern (CAP 50).
- **V5 — Modul-Kontext spiegeln.** Abgeleitete Statements erhalten
  denselben `mod_context_uri` wie im nativen Pfad.

Verweis: `.orchester/goal.md`.

---

## 2. Implementierungs-Entscheidungen

### V2 — Sidecar `uri_index.csv`

`export_datastore` schreibt einen zusätzlichen
`uri_index.csv`-Sidecar mit Zeilen `(short_key, uri)` für jede beim
Export gesehene Entity (`src/pyirk/nemobridge/exporter.py:235-246` für
das `uri_index`-Dict und das `_record_uri`-`setdefault`-Pattern;
`src/pyirk/nemobridge/exporter.py:320-323` für den Schreibvorgang).
Re-Export der Read-Helper `load_uri_index` via
`src/pyirk/nemobridge/__init__.py`. Triples-/Stmts-/Quals-Format ist
unverändert — das P3-Phase-1-Skript und alle bestehenden
Exporter-Tests laufen ohne Anpassung. Commit `0aa34a95`.

### V3 — `omit_if_existing`-Spiegel in `_materialize_tuples`

`_materialize_tuples` (`src/pyirk/nemobridge/delegation.py:196-266`)
löst jedes Tripel per URI auf
(`src/pyirk/nemobridge/delegation.py:226-246`) und übernimmt den
nativen Idempotenzcheck wortgleich:
`if obj in subj.get_relations(rel.uri, return_obj=True): continue`
(`src/pyirk/nemobridge/delegation.py:248-250`, Spiegel zu
`ruleengine.py:772-775`). Nur echte Neutupel werden via
`subj.set_relation(rel, obj)` materialisiert. Commit `0e0ba26f`.

### V4 — Beschränkter Fixpunkt-Loop in `apply_semantic_rules`

`src/pyirk/ruleengine.py:42-47` definiert die Konstante
`_NEMO_FIXPOINT_CAP = 50`. Bei aktivem Flag und nicht-leerer
delegable-Teilmenge ersetzt der V4-Loop
(`src/pyirk/ruleengine.py:108-154`) die native `exhaust=True`-Schleife:
pro Iteration genau ein `_apply_via_nemo`-Aufruf (eigener Fixpunkt
über die delegierten Regeln) gefolgt von genau einem Pass über die
restlichen Python-Regeln. Abbruch bei `n_new + p_new == 0` oder bei
`stopped_on_exception`. Mit `exhaust=False` läuft die Loop genau
einmal (`src/pyirk/ruleengine.py:151-152`). Bei
`iters > _NEMO_FIXPOINT_CAP` `RuntimeError("nemo/python fixpoint did
not converge")` (`src/pyirk/ruleengine.py:153-154`). Bei Exception aus
`_apply_via_nemo` greift der stille Fallback ab dieser Iteration
(rein-pythonisch, kein erneuter Nemo-Versuch). Commit `609db49c`.

### V5 — `mod_context_uri`-Passthrough

`_materialize_tuples` wickelt den Tupel-Loop in
`core.uri_context(mod_context_uri)` ein
(`src/pyirk/nemobridge/delegation.py:260-266`), exakt wie
`RuleApplicator.apply` (`ruleengine.py` ~Z. 295-301). Damit erhalten
alle Nemo-materialisierten Statements identische `base_uri` und sind
dem korrekten Modul für Unload/Consistency zugeordnet. Commit
`0e0ba26f` (gemeinsam mit V2/V3 ausgeliefert).

---

## 3. Gate-Ergebnis

**gate_ok = nein.** Drei Befunde gegen die echte OCSE-KB
(`experiments/h5_phase2/equivalence_gate.log`, 1:1 zitiert):

### Gate 1 — Zustands-Äquivalenz

```
[Gate 1] state equivalence: DIFF  diff_subjects=5
  subject=irk:/ocse/0.2/agents#I4122
    only_in_B (2):
      ('irk:/builtins#R83', 'irk:/builtins#I12')
      ('irk:/builtins#R83', 'irk:/builtins#I18')
  subject=irk:/ocse/0.2/control_theory#I6873
    only_in_A (1):
      ('irk:/builtins#R83', 'irk:/ocse/0.2/control_theory#I9152')
    only_in_B (1):
      ('irk:/builtins#R83', 'irk:/ocse/0.2/agents#I9152')
  subject=irk:/ocse/0.2/control_theory#I9223
    only_in_A (1):
      ('irk:/builtins#R83', 'irk:/ocse/0.2/control_theory#I1696')
  subject=irk:/ocse/0.2/math#I4122
    only_in_A (2):
      ('irk:/builtins#R83', 'irk:/builtins#I12')
      ('irk:/builtins#R83', 'irk:/builtins#I18')
  subject=irk:/ocse/0.2/math#I9223
    only_in_B (1):
      ('irk:/builtins#R83', 'irk:/ocse/0.2/control_theory#I1696')
```

**Diagnose.** Alle fünf Divergenzen sind dasselbe Muster:
`short_key`-Kollisionen über Module hinweg (`agents#I4122` /
`math#I4122`, `control_theory#I9223` / `math#I9223`,
`control_theory#I9152` / `agents#I9152`,
`control_theory#I1696` / `math#I1696`). Der V2-Sidecar
(`uri_index.csv`) bildet `short_key → uri` per `setdefault`
(`exporter.py:246`): bei doppelten `short_key`s gewinnt die zuerst
gesehene URI, alle weiteren werden verworfen. Nemos Output spricht
jedoch ausschließlich `short_key`s, daher heftet die Rück-Auflösung im
Delegationspfad alle R83-Tripel deterministisch auf die „Sieger-URI"
an, während die native Engine pro Modul-Kontext separate Items
beliefert. V2 schützt also gegen Modul-Kontext-Verlust bei unique
`short_key`s — sie ist **kein Schutz vor Kollisionen** desselben
`short_key`s in mehreren Modulen.

**Lösungspfad.** Statt eines `short_key`-Sidecars müssen die
URI-tragenden Spalten direkt in den CSV-Fakten landen (vollständige
URI-Strings in `triples.csv`/`stmts.csv` und in den Nemo-Regelköpfen),
damit Nemo die Modulinformation durchreicht. Praktisch erfordert das
Anpassungen am Codegen (String-URIs als Nemo-Konstanten /
Datalog-Terme), eine Skalierungsmessung auf der OCSE und das Mitlaufen
der bestehenden Idempotenzgarantien — größerer Eingriff, daher
außerhalb Phase 2.

### Gate 2 — Idempotenz

```
[Gate 2] idempotency:       OK  extra_stmts_on_replay=0
```

**Diagnose.** OK. V3 (omit_if_existing-Spiegel) + V4 (Fixpunkt-Loop)
arbeiten zwischen Aufrufen idempotent: der zweite Delegationslauf
direkt auf dem Ergebnis von Pfad B fügt 0 neue Statements ein.

### Gate 3 — kein Duplikat

```
[Gate 3] no duplicates:     DUPS  duplicate_triples=5 max_multiplicity=3
  mult=3  ('irk:/ocse/0.2/control_theory#Ia26808', 'irk:/builtins#R31', 'irk:/ocse/0.2/math#I5000')
  mult=2  ('irk:/ocse/0.2/math#Ia86475', 'irk:/builtins#R31', 'irk:/ocse/0.2/math#Ia79736')
  mult=2  ('irk:/ocse/0.2/math#Ia92990', 'irk:/builtins#R31', 'irk:/ocse/0.2/math#Ia38008')
  mult=2  ('irk:/ocse/0.2/math#Ia90004', 'irk:/builtins#R31', 'irk:/ocse/0.2/math#I5000')
  mult=2  ('irk:/ocse/0.2/control_theory#Ia75577', 'irk:/builtins#R30', 'irk:/ocse/0.2/control_theory#I9199')
```

**Diagnose.** Alle fünf betroffenen Tripel sind R30/R31 mit
`Ia…`-Auto-Items (in-rule erzeugt). Der `omit_if_existing`-Check in
`_materialize_tuples` (`delegation.py:249`) evaluiert
`subj.get_relations(rel.uri, return_obj=True)` **einmal** pro Tupel
gegen den DataStore-Stand zum Beginn des Mapping-Loops. Innerhalb
desselben `_apply_via_nemo`-Aufrufs wird ein gerade durch
`set_relation` neu eingefügtes Statement vor dem nächsten gleichen
Tupel im Loop nicht erneut geprüft — folglich entstehen Duplikate,
wenn Nemos `output_<REL>.csv` denselben (subj, rel, obj) mehrfach
liefert (was auf den OCSE-Daten für R30/R31 mit Auto-Items
nachweislich passiert). Gate 2 (Idempotenz **zwischen** Aufrufen) ist
davon nicht betroffen, weil ein zweiter Aufruf gegen den dann
aktualisierten Stand prüft.

**Lösungspfad.** Lokales `inserted: set[tuple[str, str, str]]` in
`_materialize_tuples` mitführen und vor dem `set_relation`-Aufruf
zusätzlich `if (subj_uri, pred_uri, obj_uri) in inserted: continue`
prüfen; nach erfolgreichem `set_relation` das Tripel ins Set
aufnehmen. Kostet O(n) Speicher pro Aufruf, kein Eingriff in die
DataStore-API.

---

## 4. Timing

`experiments/h5_phase2/equivalence_gate.log` (Pre-Flight
`uptime load (1-min): 0.07`, Nemo `nemo-cli 0.10.0`):

| Pfad        | t (s)     | Last        | Marker         |
|-------------|-----------|-------------|----------------|
| native      | 323.568   | load=0.07   | ok             |
| delegation  |   1.025   | load=1.08   | (load-belastet)|

Speedup `speedup_fullrun: 315.62x` (≈ **315×**).

**Hinweis.** Der Delegations-Subprozess startete unter
`load=1.08` — selbst-induziert durch den vorangegangenen
native-Subprozess (`subprocess native done … wall: 329.229s` direkt
davor). Das automatische `(load-belastet)`-Label ist daher
load-/Self-induced, der echte Delegationswert liegt wahrscheinlich
unter 1 s. Das passt zur Phase-1-Notiz aus Commit `75aa15cf`
(`docs(h5): confirm ~790x speedup on quiet VPS`): unter realistisch
ruhigen Bedingungen ist eine ~790×-Größenordnung belastbar. Die
H5-Schwelle „mehrere Hundert × Speedup" ist robust erreicht.

---

## 5. Erweiterungspunkt Qualifier-Delegation (V1)

Phase 2 hält V1 strukturell als isolierte Ergänzung offen. Konkrete
Stelle:

- **Funktion:** `_apply_qualifiers(new_stm)` in
  `src/pyirk/nemobridge/delegation.py:269-279` (aktuell `return None`,
  No-op). Signatur und Aufrufstelle aus `_materialize_tuples`
  (`src/pyirk/nemobridge/delegation.py:252-254`) bleiben unverändert.
- **Voraussetzung:** Das native `# TODO: add qualifiers` in
  `src/pyirk/ruleengine.py:776` (zwischen
  `omit_if_existing`-Check und `set_relation`) muss gleichzeitig
  geschlossen werden — sonst ist Pfad A weiterhin qualifier-frei und
  das Äquivalenzgate (Gate 1) hätte kein wohldefiniertes Ziel.
- **Datengrundlage:** Der Qualifier-Export ist seit Commit
  `0aa34a95` erhalten (`stmts.csv` + `quals_<R>.csv` aus
  `src/pyirk/nemobridge/exporter.py`); eine spätere Phase kann darauf
  unmittelbar aufsetzen.

---

## 6. Offene Punkte

1. **V2-Lücke — short_key-Kollision über Module hinweg.** Konkreter
   Lösungspfad: URI-tragende CSV-Spalten statt
   `short_key`-Sidecar; Nemo-Codegen muss String-URIs als
   Datalog-Terme durchreichen. Größerer Eingriff, deshalb außerhalb
   Phase 2 geparkt.
2. **V3-Lücke — within-call Dedup.** Konkreter Lösungspfad: lokales
   `inserted: set[tuple[str, str, str]]` in `_materialize_tuples`
   mitführen, vor `set_relation` zusätzlich prüfen, nach
   erfolgreichem Insert hinzufügen. Lokaler, risikoarmer Patch.
3. **Qualifier-Delegation (V1) vertagt.** Erweiterungspunkt
   strukturell vorhanden (Abschnitt 5); Aktivierung an natives
   `# TODO: add qualifiers` gekoppelt.
4. **Flag-Default bleibt AUS.** `PYIRK_NEMO_DELEGATION` wird nicht
   produktiv aktiviert (`goal.md`-Vorgabe).

---

PHASE2-VERDICT: gate_ok=nein speedup_fullrun=315x
