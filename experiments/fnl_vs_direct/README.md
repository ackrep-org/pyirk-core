# Experiment: FNL vs. direct (LaTeX → pyirk)

## Ziel des Experiments

Vergleiche fuer zwei mathematische Korpora die zweistufige Pipeline
**LaTeX → FNL → pyirk** (formalisierte Naturalsprache als Zwischenebene)
gegen den direkten Pfad **LaTeX → pyirk**. Auswertet wird je Statement-Typ,
fuer welche der direkte Pfad zuverlaessig genug ist (`direct_viable_types`)
und fuer welche eine FNL-Zwischenstufe als Checkpoint noetig bleibt
(`checkpoint_needed_types`). Methodisch fixiert sich das Experiment an
`corpus_gold__gitignore__/bernstein/goal.md` (das `chunk_full_source.tex`
ist der zugehoerige Quelltext).

## Korpora

| Korpus | LaTeX-Quelle | LaTeX-Marker (`\snippet{ID}`) | FNL-Gold-Datei | FNL-Snippets | pyirk-Gold vorhanden | Tiefe |
|---|---|---|---|---|---|---|
| nichtlinear | `corpus_gold__gitignore__/nichtlinear/kapitel2.tex` | 74 | `formalized_statements_nl.md` | 64 (5 davon `*i` = ignored) | ja (`pyirk_gold.py` mit `__URI__ = "irk:/auto_import_formalized_statements_nl"`) | 3 Ebenen (LaTeX / FNL / pyirk) |
| bernstein   | `corpus_gold__gitignore__/bernstein/chunk_full_source.tex` | 106 | `formalized_statements0.md` | 52 (9 davon `*i` = ignored) | nein | 2 Ebenen (LaTeX / FNL) |

Die Korpora liegen unter `corpus_gold__gitignore__/` und sind git-ignoriert
(Suffix `__gitignore__` im Verzeichnisnamen ⇒ vom Repo ausgenommen). Das
Experiment selbst ist auf diese Verzeichnisstruktur angewiesen, aber nicht
auf konkrete Versionen der Dateien.

## Snippet-Auswahl

Erzeugt durch `experiments/fnl_vs_direct/snippet_selection.py`:

* deterministisch (kein RNG; `seed` ist nur fuer Interface-Stabilitaet im
  Signaturschluessel mitgefuehrt),
* typ-quotiert (Ziel: je ca. 1/3 leichte / mittlere / schwere Typen),
* `*i`-Snippets werden vor der Auswahl ausgesondert,
* Auswahl innerhalb eines Buckets per `sorted(snippet_ids)` und `[::stride]`
  (kein Shuffle),
* harte Schranke: `20 <= n <= 30` je Korpus (Zielgroesse 25).

Reproduktion:

```bash
/home/user/venvs/pyirk-core-venv/bin/python -m experiments.fnl_vs_direct.snippet_selection
```

schreibt `experiments/fnl_vs_direct/snippet_selection.json` mit den
ausgewaehlten Snippet-IDs je Korpus (siehe JSON-Datei).

## Statement-Typ-Taxonomie

Die folgenden 9 Kategorien werden vom deterministischen
`tag_snippet(snippet_id, fnl_text)`-Heuristik vergeben (Prioritaet
heaviest first; das schwerste passende Tag gewinnt):

| Tag | Definition (Heuristik) |
|---|---|
| `definition_or` | FNL-Block enthaelt eine `- OR`-Zeile (Disjunktions-Definition). |
| `definition_and` | FNL-Block enthaelt eine `- AND`-Zeile (Konjunktions-Definition). |
| `equivalence` | FNL-Block enthaelt `equivalence-statement`, `if and only if` oder `iff`. |
| `qualified` | FNL-Block enthaelt `qqq` (Quantor-Qualifier), `is a qualifier` oder `For all/each/every`. |
| `subclass` | `is a subclass of` / `is a subproperty of`. |
| `instance` | `is an instance of` / `is instance of`. |
| `notation` | `has the associated LaTeX notation` / `has notation`. |
| `declaration` | Fallback: `There is a class/relation/property/operator` etc. |
| `ignored` | Snippet-ID endet auf `i`; nicht ausgewaehlt. |

Quoten-Buckets: `light = {declaration, notation, instance, subclass}`,
`medium = {equivalence, qualified}`, `heavy = {definition_and,
definition_or}`. Wenn ein Bucket zu klein ist (kommt in beiden Korpora vor
— `heavy` ist in Korpus B nur 3 Snippets gross, `medium` in Korpus A 8 von
ueber 50 nicht-ignored), wird das verbleibende Kontingent in der Reihenfolge
`light → medium → heavy` aufgefuellt.

## Schwellen (vorab fixiert, nicht nachtraeglich passen!)

* **Validitaet >= 90 %** je Statement-Typ: ein erzeugtes Snippet zaehlt als
  valide, wenn es per `validate_module` einen Round-Trip ohne Fehler
  durchlaeuft.
* **Faithfulness** je Snippet:
  * **Korpus A** (`nichtlinear`): struktureller Diff gegen das pyirk-Gold
    (`pyirk_gold.py`, URI `irk:/auto_import_formalized_statements_nl`)
    `== 0`. Wenn der Diff Null ist, gilt das Snippet als treu uebertragen.
  * **Korpus B** (`bernstein`) bzw. wenn kein pyirk-Gold vorliegt: LLM-Judge
    auf Basis der erzeugten pyirk-Repraesentation **plus** Spotcheck-Eintrag
    fuer spaetere menschliche Review.

Ein Statement-Typ landet in `direct_viable_types`, wenn **beide** Kriterien
auf dem Typ-Bucket erfuellt sind; sonst in `checkpoint_needed_types`. Die
Schwellen stehen identisch in `snippet_selection.json` (Feld `thresholds`)
und sind dort als maschinenlesbare Referenz festgeschrieben.

## Modellwahl

Sowohl der scharfe Lauf (Snippet-Verarbeitung) als auch der LLM-Judge
nutzen **Opus** (`claude-opus-4-7`); der Substrat-Default `sonnet` aus den
pyirk-Skripten wird fuer dieses Experiment explizit ueberschrieben. Damit
ist sichergestellt, dass der direkte Pfad nicht durch ein schwaecheres
Modell benachteiligt wird und der Judge sich am gleichen Niveau orientiert.

## Limitationen-Vorbemerkung

* Der LLM-Judge ist fehleranfaellig; falsch-positive oder falsch-negative
  Aequivalenz-Urteile sind moeglich. Spotcheck-Auszuege werden deshalb
  **vorbereitet** und in einer Review-Datei gesammelt — der menschliche
  Review erfolgt aber **nach** dem Lauf, nicht in-the-loop.
* Korpus B hat keinen pyirk-Goldstand; dort gibt es keinen strukturellen
  Diff als objektive Backstop-Metrik. Die Faithfulness-Entscheidung haengt
  damit ausschliesslich an LLM-Judge + Spotcheck.
* Die Typ-Heuristik (`tag_snippet`) ist bewusst simpel (Regex/Keyword).
  Sie ist deterministisch und reproduzierbar, kann im Einzelfall aber
  falsch klassifizieren — primaer relevant fuer Buckets, in denen ein
  schwerer Typ knapp ist (z. B. `definition_or` in Korpus A: 0 Treffer).
* Die Korpus-Verzeichnisse sind git-ignoriert; das Experiment ist nur
  reproduzierbar, wenn die FNL-Gold-Dateien lokal verfuegbar sind.

## Pflicht-Schlusszeilen-Format

Am Ende des Auswertungslaufs ist genau **eine** Zusammenfassungszeile in
folgendem Format auszugeben:

```
FNLVSDIRECT-VERDICT: direct_viable_types=<liste> checkpoint_needed_types=<liste> n_A=<N_nichtlinear> n_B=<N_bernstein>
```

`<liste>` ist eine komma-separierte Aufzaehlung der Typ-Tags (ohne
Leerzeichen), `n_A`/`n_B` sind die Anzahlen der tatsaechlich verarbeiteten
Snippets je Korpus.
