# Phase 5 -- Prompt-Header-Entscheidung fuer den LaTeX-Adapter

## Substrat-Prompt

Der generische `import_one_statement`-Pfad in `src/pyirk/authoring/__init__.py`
baut den LLM-Prompt in `build_import_prompt(...)` zusammen. Die Vorlage hat die
Form

    PROMPT_HEADER + Source/URI/Theorem/Hits/Index/Module-Summary + PROMPT_RULES

`PROMPT_HEADER` wird vor dem Aufruf des `build_import_prompt` als Modul-Konstante
aufgeloest -- es gibt KEINEN Funktions-Parameter, mit dem ein Adapter einen
eigenen Header durchreichen koennte. `lean.py` und `latex.py` rufen
`import_one_statement` mit denselben Keyword-Args auf; der Header ist also
implizit fuer beide derselbe.

Inhaltlich ist der vorhandene `PROMPT_HEADER` Lean-getunt:

* Sein "Worked Example" zeigt den **Satz des Pythagoras (Seitenform)** in der
  pyirk-iff-Codierung (`R4__is_instance_of=p.I17["equivalence proposition"]`,
  drei Scopes `setting`/`premise`/`assertion`, `st.new_equation(lhs=..., rhs=...)`).
* Die "Key idioms"-Liste zielt auf typische Lean-Faelle: typgebundene
  Variablen (`(x y : V)`) -> `p.uq_instance_of(<entity>)` im Setting,
  Reuse von `ma.I2917 planar triangle` etc.
* `R24__has_LaTeX_string` taucht im Substrat-Header NICHT auf -- Lean-Theoreme
  haben kein eigenes Notations-Konzept.

Der LaTeX-Adapter (`src/pyirk/authoring/latex.py`, vor diesem Task) reichte den
unveraenderten Substrat-Header durch.

## Korpus-Stichprobe

Sechs Snippets aus den beiden Korpora wurden gegen das Lean-Worked-Example
gehalten. IDs gemaess `\snippet{N}` im jeweiligen `.tex`.

### Korpus A -- `nichtlinear/kapitel2.tex` (deutsch, Regelungstheorie)

* **#4** (Typ `subclass`): "Der $n$-dimensionale reelle Vektorraum wird mit
  ${\mathbb{R}}^{n}$ bezeichnet, seine Elemente heissen \textbf{\em Vektoren}."
  -- Eine **Klassen-/Subklassen-Einfuehrung** mit gebundener LaTeX-Notation
  (`\mathbb{R}^n`) und Synonym ("Vektoren"). Kein iff, kein implies. Ziel-pyirk
  ist `p.create_item(R3__is_subclass_of=..., R24__has_LaTeX_string=...)`.
* **#8** (Typ `qualified`): "Jeder Vektor ... laesst sich eindeutig als
  Linearkombination der Basisvektoren darstellen: $x=x_1 e_1+\cdots+x_n e_n$."
  -- Eine quantifizierte Aussage ("Jeder ... laesst sich ...") mit inline
  LaTeX-Gleichung. Sehr **prosa-lastig**, kaum Lean-aehnlich; passt am ehesten
  auf einen general-statement-Scope, nicht auf I17/I15.
* **#19** (Typ `subclass`): "Gilt $m=n$, so spricht man von einer
  \textbf{\em quadratischen} Matrix." -- Ein bedingter Subklassen-Begriff.
  Bilingual implizit (deutsche Prosa, kein expliziter englischer Tag).
* **#20** (Typ `definition_and`): "Die $n\\times n$\textbf{\em -Einheitsmatrix}
  (engl. \textbf{\em identity matrix}) wird mit $I_n$ bzw. mit $I$ bezeichnet.
  Bei ihr sind die Hauptdiagonalelemente Eins, alle anderen Elemente Null."
  -- Zwei Aussagen in einem Snippet: **Instanz-Deklaration** mit
  bilingualem Label und LaTeX-Symbol PLUS strukturelle Definition. Lean-Worked-
  Example hilft hier nichts.

### Korpus B -- `bernstein/chunk_full_source.tex` (englisch, lineare Algebra)

* **#4** (Typ `declaration`): "A *set* $\\{x,y,\\ldots\\}$ is a collection of
  elements. ... The set $\\SX$ is *finite* if it has a finite number of
  elements; otherwise, $\\SX$ is *infinite*." -- Klassen-Einfuehrung mit
  Eigenschaften (`finite`, `infinite`). Mehrere Konzepte in einem Snippet.
* **#6** (Typ `notation`): "Let $\\SX$ be a set. Then, $x \\in \\SX$ means that
  $x$ is an *element* of $\\SX$." -- Klassische Notations-Einfuehrung mit
  Relation `is element of` und LaTeX-Notation `\\in`.

### Strukturell anders als Lean

1. **Dominante Faelle sind keine Theoreme**, sondern Klassen-, Instanz-,
   Operator- und Notations-Deklarationen. Das I17/I15-Scope-Muster im Lean-
   Beispiel passt nur fuer einen Bruchteil (Bernstein #14/#15, evtl. einzelne
   Nichtlinear-`equivalence`-Snippets).
2. **`R24__has_LaTeX_string` ist zentral** -- ein Mathebuch lebt von Symbolik
   (`\\cap`, `\\varnothing`, `\\mathbb{R}^n`, `I_n`). Der Lean-Header zeigt das
   nicht.
3. **Bilingualitaet** (deutsch/englisch nebeneinander) ist in Korpus A die
   Regel, nicht die Ausnahme.
4. **Prosa und Mathe sind verwoben**: Statt sauberer Typ-Signaturen wie in Lean
   gibt es Saetze, die ein Konzept einfuehren und dann beilaeufig eine
   Eigenschaft zuschreiben. Das LLM braucht Anker fuer "wie sieht eine
   Klassen-/Subklassen-Deklaration in pyirk aus?" und "wie haengt man die
   LaTeX-Notation an?".
5. **Mehrfach-Definitionen pro Snippet** (Bernstein #4 erzeugt
   `set`/`finite`/`infinite` in einem Atemzug; Nichtlinear #20 erzeugt
   `identity matrix` plus Diagonal-Spezifikation).

## Entscheidung

**Wir fuehren `LATEX_PROMPT_HEADER` in `src/pyirk/authoring/latex.py` ein** und
ersetzen damit den Substrat-Header fuer LaTeX-Snippet-Imports.

Begruendung: Das Worked Example praegt den Output am staerksten. Solange der
einzige sichtbare Spickzettel ein Pythagoras-iff-Theorem ist, wird Opus
LaTeX-Mathe-Snippets entweder (a) gewaltsam in eine I17/I15-Form pressen
oder (b) ohne Vorlage fuer Klassen-/Notations-/Operator-Idiome frei
improvisieren -- in beiden Faellen mit hoher Validierungs-Ausfallrate. Da
~90% der ausgewaehlten Snippets in beiden Korpora **Deklarationen** (class,
subclass, instance, notation, operator) statt Theoreme sind, ist der
Erwartungswert eines Mathe-Worked-Examples deutlich groesser als der eines
Pythagoras-Theorems.

Das neue Worked Example zeigt drei Faelle aus einem Atemzug: (1) eine
Subklasse von `p.I13["mathematical set"]`, (2) einen binaeren Operator
`set intersection` mit Domain/Range UND `R24__has_LaTeX_string`, (3) eine
Instanz `empty set` mit ihrem Symbol. Das deckt drei der vier dominanten
Snippet-Typen direkt ab.

Die iff/implies-Pattern bleibt in der Idiomliste erwaehnt (mit Verweis auf
`p.I17` / `p.I15` und drei Scopes), damit Bernstein-#14/#15 und Nichtlinear-
`equivalence`-Snippets weiterhin encodierbar sind -- nur eben nicht mehr als
einziger Anker.

## Implementierung

* `LATEX_PROMPT_HEADER` ist eine Modul-Konstante in
  `src/pyirk/authoring/latex.py`.
* Da das Substrat den Header nicht parametrisiert (nur Modul-Konstante
  `PROMPT_HEADER`), tauscht der Adapter den Wert per Context-Manager
  `_swap_prompt_header(...)` fuer die Dauer des `import_one_statement`-
  Aufrufs in `pyirk.authoring` aus und stellt ihn danach wieder her.
  Damit bleibt der Lean-Adapter (`pyirk.authoring.lean.import_theorem`)
  unveraendert auf seinem Lean-getunten Header -- keine Substrat-Edits
  noetig.
* `import_snippet(...)` ist die einzige Aufruf-Stelle und nutzt den
  Context-Manager intern.

Tests in `tests/test_latex_prompt.py` (tokenfrei, < 2 s):

1. `LATEX_PROMPT_HEADER` enthaelt die erwarteten Marker (Worked-Example-
   Labels, `p.I13["mathematical set"]`, `R24__has_LaTeX_string` mit
   `arg1`/`arg2`-Placeholdern, `R8`/`R11`, Arity-Items `I7`/`I8`/`I9`, sowie
   `I17`/`I15` als Erinnerung an die iff-Pattern).
2. Der neue Header ist NICHT mit `PROMPT_HEADER` identisch und enthaelt
   keine Lean-Restartefakte ("Pythagorean theorem", "planar triangle").
3. `_swap_prompt_header` ist sauber gescoped und wird auch bei Exceptions
   restauriert.
4. `import_snippet(...)` macht den Mathe-Header waehrend des Substrat-
   `build_import_prompt`-Aufrufs sichtbar (Substrat per `monkeypatch`
   gestubbed, Erfolgsfall).
5. Regression: nach `import_snippet(...)` -- auch bei Aufgabe nach
   `max_attempts` mit malformed responses -- ist
   `pyirk.authoring.PROMPT_HEADER` wieder auf seinem Lean-Wert.

Bestehende Tests (`tests/test_latex_adapter.py`, `tests/test_snippet_selection.py`,
`tests/test_fnl_vs_direct_metrics.py`, `tests/test_structural_diff.py`,
`tests/test_judge_harness.py`) bleiben gruen.

## Risiken / offene Punkte

* **Worked-Example-Bias**: Auch ein neues Worked Example praegt. Wenn das
  Beispiel `set intersection` zeigt, koennte Opus dazu neigen, ueberall
  set-basierte Domains anzunehmen. Der Nichtlinear-Korpus ist aber
  Vektorraum-/Matrix-zentriert -- Drift muss in Phase 6 beobachtet werden
  (Validierungs-Rate auf Snippets #4, #6, #19, #20 vs. Bernstein #4, #6, #8).
* **Iff-/Implies-Snippets** (Bernstein #14, #15; ggf. Nichtlinear #12, #14)
  verlieren das prominente Worked Example. Sie bleiben in der Idiomliste
  erwaehnt, aber ohne fertigen Code-Schnipsel. Falls die Aussagen-Snippets
  in Phase 6 reihenweise FORK/Validation-Fail produzieren, ist eine
  zweiteilige Worked-Example-Sektion (deklarations- + iff-Beispiel) die
  naheliegende Iteration.
* **`R24` und `arg1/arg2`-Konvention**: Das Substrat selbst macht keinerlei
  Aussage darueber, wie Mehrfach-Argument-Notationen verklebt werden. Die
  hier gewaehlte Konvention (`r"$arg1 \cap arg2$"`) ist innerhalb des
  Prompts dokumentiert, hat aber keinen Rueckhalt in `builtin_entities.py`.
  Falls die OCSE eine andere Konvention verlangt, muss der Header
  nachgeschaerft werden -- in Phase 6 ueber die strukturelle Diff (Korpus A)
  sichtbar.
* **Bilingualitaet ist nur informell adressiert**: Der Header empfiehlt
  englische R1-Labels und beilaeufige Erwaehnung der deutschen Form in R2.
  Eine echte `alt_label`-Relation in der OCSE waere besser, falls vorhanden;
  der Header verweist auf den Dependency-Index, ohne eine konkrete Relation
  zu nennen.
* **Globale Modul-Konstante als Swap-Target**: Mehrere parallele
  `import_snippet`-Calls auf demselben Substrat-Modul wuerden sich gegenseitig
  ihre PROMPT_HEADER-Werte ueberschreiben. Aktuell unkritisch (Phase 6 laeuft
  seriell), aber bei spaeterer Parallelisierung muesste das Substrat
  parametrisiert werden -- aus diesem Adapter heraus nicht moeglich.
