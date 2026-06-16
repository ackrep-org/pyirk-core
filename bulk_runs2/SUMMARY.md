# Bulk-Run-2 Auswertung: Drei Lean-Import-Korpora

Generiert aus den Stats-Dateien in `bulk_runs2/{eigenspace,trace,ode_transform}/stats.jsonl`.
Vergleichsdaten für Run 1 stammen aus `bulk_runs/SUMMARY.md`.

---

## A. Metriken pro Korpus (Run 2)

| Korpus | Total | ok | failed | error | FORK-Rate | Val-Retry-Rate | Mean dur (s) | Max dur (s) | Σ cost_usd | Σ n_claude_calls | Σ n_key_remaps |
|--------|-------|----|--------|-------|-----------|----------------|--------------|-------------|------------|------------------|----------------|
| eigenspace | 35 | 30 | 3 | 2 | 88,6 % (31/35) | 17,1 % (6/35) | 299,9 | 694,5 | 12,37 $ | 78 | 14 |
| trace | 35 | 32 | 2 | 1 | 77,1 % (27/35) | 14,3 % (5/35) | 238,1 | 1036,4 | 10,30 $ | 73 | 13 |
| ode_transform | 19 | 18 | 1 | 0 | 42,1 % (8/19) | 26,3 % (5/19) | 224,3 | 804,1 | 5,72 $ | 34 | 0 |

- **FORK-Rate**: Anteil der Theoreme mit mindestens einem `fork`-Event.
- **Val-Retry-Rate**: Anteil der Theoreme mit mindestens einem `validation_fail`-Event.
- **Σ n_key_remaps**: Gesamtanzahl automatischer Index-Remappings über alle Theoreme des Korpus.

---

## B. Vergleich Run 1 vs. Run 2

| Korpus | Run 1 ok | Run 1 failed | Run 1 error | Run 2 ok | Run 2 failed | Run 2 error | Δ ok |
|--------|----------|-------------|------------|----------|-------------|------------|------|
| eigenspace | 20 | 14 | 1 | 30 | 3 | 2 | **+10** |
| trace | 27 | 8 | 0 | 32 | 2 | 1 | **+5** |
| ode_transform | 19 | 0 | 0 | 18 | 1 | 0 | **−1** |

### Kollisions-Kaskaden-Fehlerklasse ('AssertionError ... already occupied')

**In Run 2 ist diese Fehlerklasse vollständig verschwunden.**

In Run 1 stellten `AssertionError: ... already occupied`-Fehler die dominierende Fehlerursache dar:
- eigenspace: mind. 10 von 15 Fehlern waren Index-Kollisions-Kaskaden (I73, I80 u.a.)
- trace: mind. 6 von 8 Fehlern waren Kollisions-Kaskaden (I3051, I3060 u.a.)

Eine manuelle Prüfung sämtlicher `error`- und `failed`-Records in Run 2 ergibt: **kein einziger
Fehlertext enthält 'already occupied'**. Der in Commit `354862b0` (pipeline-owned key-collision
remapping) und `d4cf6198` (--collide-every flag) implementierte Key-Remap-Mechanismus greift
zuverlässig: Statt in einen Kollisionsfehler zu laufen, werden kollidierte Item-Indizes automatisch
auf freie Slots umgezogen (eigenspace: 14 Remaps, trace: 13 Remaps). Die überwiegende Mehrheit
dieser Theoreme schließt danach mit `ok` ab.

---

## C. FORK-Fragen (alle Events)

| # | Korpus | Theorem | Frage (gekürzt) | Gewählt |
|---|--------|---------|-----------------|---------|
| 1 | eigenspace | mem_genEigenspace | M als R-Modul: `ma.I5166["vector space"]` (Körper-Einschränkung) oder neue Ring/Modul-Items? | a |
| 2 | eigenspace | genEigenspace_directed | `f : End R M` fehlt im Index — neues "module endomorphism"-, "linear endomorphism"- oder Operator-Item? | a |
| 3 | eigenspace | mem_genEigenspace_nat | `x ∈ ker((f−μ·1)^k)` als RHS: Iterierte-Kern-Formel oder direkter Operator-Ausdruck? | a |
| 4 | eigenspace | mem_genEigenspace_top | `∃ k : ℕ, x ∈ ker(...)`: Existenzquantifikation in Assertionsscope — wie kodieren? | a |
| 5 | eigenspace | genEigenspace_nat | Reine Mengengleichheit ohne Hypothese — welcher Propositions-Typ (`I15`/`I17`/anderer)? | a |
| 6 | eigenspace | genEigenspace_eq_iSup_genEigenspace_nat | Exponent `k : ℕ∞` (erweiterte Natürliche Zahl) — Untertyp-Item oder Reuse `I3["extended natural number"]`? | a |
| 7 | eigenspace | genEigenspace_top | `I1010` als "iSup bis k" — beschränkter oder unbeschränkter Supremum-Operator? | a |
| 8 | eigenspace | genEigenspace_one | Typ von `μ : R` (skalarer Eigenwert) im Setting — welches pyirk-Item? | a |
| 9 | eigenspace | mem_genEigenspace_one | IFF mit Mengenzugehörigkeit links und `f x = μ • x` rechts — wie Bikonditional kodieren? | a |
| 10 | eigenspace | mem_genEigenspace_zero | `0 : M` (Modulnull) — `ma.I5000["scalar zero"]` wiederverwenden oder neues Modul-Zero-Item? | a |
| 11 | eigenspace | genEigenspace_zero | `⊥` (triviales Untermodul) — benanntes Constant-Item, strukturelles `ker(id)` oder Proxy? | a |
| 12 | eigenspace | UnifEigenvalues.val_mk | `HasUnifEigenvalue μ k` und `UnifEigenvalues.val` fehlen — wie einführen? | a |
| 13 | eigenspace | UnifEigenvalues.mk_val | `⟨μ.val, μ.property⟩ = μ`: Untertyp-Konstruktor ohne pyirk-Primitiv — wie modellieren? | a |
| 14 | eigenspace | HasUnifEigenvector.hasUnifEigenvalue | `HasUnifEigenvector μ k x` (4-stellig) — wie in Premissen-Scope kodieren? | a |
| 15 | eigenspace | HasUnifEigenvalue.exists_hasUnifEigenvector | `∃ v, HasUnifEigenvector μ k v` — Existenz in Assertionsscope | a |
| 16 | eigenspace | HasUnifEigenvalue.pow | `HasUnifEigenvalue f μ 1` (Exponent fixiert auf 1) — wie Prädikat typisieren? | a |
| 17 | eigenspace | HasUnifEigenvalue.isNilpotent_of_isNilpotent | `IsNilpotent` doppelt: auf Endomorphismus (Prämisse) und Skalar (Konklusion) — ein oder zwei Items? | a |
| 18 | eigenspace | HasUnifEigenvalue.mem_spectrum | `μ ∈ spectrum R f` — neue Mengen-Operator + Zugehörigkeit oder binäres Prädikat? | a |
| 19 | eigenspace | hasUnifEigenvalue_iff_mem_spectrum | `μ ∈ spectrum K f` rechts — Spektrum-Item für lineare Endomorphismen? | a |
| 20 | eigenspace | genEigenspace_div | Eigenwert `a / b` (Skalardivision) — kein Arithmetik-Überladen für Module; neuer binärer Operator? | a |
| 21 | eigenspace | HasUnifEigenvalue.exp_ne_zero | `k ≠ 0` in Assertionsscope — neues `is_nonzero`-Prädikat oder `not_equal`-Operator? | a |
| 22 | eigenspace | genEigenspace_top_eq_maxUnifEigenspaceIndex | `[IsNoetherian R M]` Typklassen-Constraint — Untertyp im Setting oder boolesches Prädikat? | a |
| 23 | eigenspace | genEigenspace_le_genEigenspace_maxUnifEigenspaceIndex | `[IsNoetherian R M]` — wie in pyirk kodieren? | a |
| 24 | eigenspace | genEigenspace_eq_genEigenspace_maxUnifEigenspaceIndex_of_le | `maxUnifEigenspaceIndex` (Funktion End R M → R → ℕ) + Ungleichungs-Prämisse | a |
| 25 | eigenspace | HasUnifEigenvalue.le | Ordnungs-Prämisse `k ≤ m` über `ℕ∞` im Prämissen-Scope | a |
| 26 | eigenspace | HasUnifEigenvalue.lt | Prämisse `0 < m` (für `m : ℕ∞`) — neues Positivitäts-/Ordnungs-Item? | a |
| 27 | eigenspace | hasUnifEigenvalue_iff_hasUnifEigenvalue_one | IFF zwischen zwei Anwendungen von `HasUnifEigenvalue` — drei Enkodierungsvarianten | a |
| 28 | eigenspace | maxUnifEigenspaceIndex_le_finrank | Konklusion ist Ungleichung (`≤`), kein Gleichung — welche Scope-API? | a |
| 29 | eigenspace | genEigenspace_le_genEigenspace_finrank | `finrank K V` (endliche Dimension) als pyirk-Term | a |
| 30 | eigenspace | genEigenspace_eq_genEigenspace_finrank_of_le | `finrank K V` auf RHS und in Prämisse — unärer Operator oder explizite Dimensionsvariable? | a |
| 31 | eigenspace | mapsTo_genEigenspace_of_comm | `Commute f g` (Prämisse) + `MapsTo g S S` (Konklusion) — Kompositionsgleichung oder boolesche Prädikate? | a |
| 32 | trace | traceAux_def | `Matrix.trace` — bloßer unärer Operator oder Eltern-Typ mit `ma.I5359["determinant"]` teilen? | a |
| 33 | trace | traceAux_eq | `[CommRing R]` — kein "kommutativer Ring" in Index; neues Item oder Näherung durch Körper? | a |
| 34 | trace | trace_eq_matrix_trace | Unbedingte Gleichheit `trace_M = ...` — `p.I15` mit Typ-Deklarationen oder nacktes Proposition? | a |
| 35 | trace | trace_mul_comm | `f * g` (Komposition) — neues Kompositions-Item oder pyirk-überladen `*`? | a |
| 36 | trace | trace_lie_mul_eq | Lie-Klammer `⁅f,g⁆ = f*g - g*f` — domain-spezifisch oder abstraktes Lie-Algebra-Item? | a |
| 37 | trace | trace_conj | Invertierbarkeit von `f` als `(M →ₗ M)ˣ` — neues Untertyp-Item + Inverse-Operator? | a |
| 38 | trace | trace_eq_contract_of_basis | `dualTensorHom` und `contractLeft` fehlen — minimal untypisiert, volle Typhierarchie oder nur Domäne? | a |
| 39 | trace | trace_eq_contract_of_basis' | `(dualTensorHomEquivOfBasis b).symm.toLinearMap` auf RHS kodieren | a |
| 40 | trace | trace_eq_contract | Funktionsgleichheit `trace ∘ₗ dualTensorHom = contractLeft` — neuer Kompositions-Operator oder punktweise? | a |
| 41 | trace | trace_eq_contract' | `dualTensorHomEquiv R M M` (kanonik, basisfrei) — wie modellieren? | a |
| 42 | trace | trace_one | `finrank R M` (Rang von M über R, nach R gecastet) als verwendbarer Term in `new_equation` | a |
| 43 | trace | trace_id | Modul `M` im Setting — `[Module.Free R M]` als Untertyp-Item oder boolesche Prämisse? | a |
| 44 | trace | trace_transpose | `trace R (Dual R M) ∘ₗ transpose = trace R M` — zwei lineare Abbildungen als Funktionsobjekte | a |
| 45 | trace | trace_prodMap' | Zwei verschiedene R-Moduln M und N plus `prodMap`-Operator | a |
| 46 | trace | trace_tensorProduct | Bilineare-Abbildungs-Gleichheit `(End M × End N) →ₗ R` — Literal oder semantische Abkürzung? | a |
| 47 | trace | trace_prodMap | Gleichheit zweier lineare Abbildungen `End(M) × End(N) →ₗ R` — welche Enkodierung? | a |
| 48 | trace | trace_comp_comm | `f : M →ₗ N`, `g : N →ₗ M` zwischen verschiedenen Moduln — neuer Typ oder Endomorphismus-Reuse? | a |
| 49 | trace | trace_transpose' | `Module.Dual.transpose` (dual-Transponierungsoperation) — eigenständig oder ableiten? | a |
| 50 | trace | trace_tensorProduct' | `map f g` (induzierter Endomorphismus auf `M ⊗ N`) — wie darstellen? | a |
| 51 | trace | trace_smulRight | `smulRight` (Rang-1-Endomorphismus-Konstruktor) fehlt im Index — minimales Item oder Typhierarchie? | a |
| 52 | trace | trace_comp_cycle | Drei verschiedene Modultypen M, N, P über Ring R — wie in Setting strukturieren? | a |
| 53 | trace | IsProj.trace | `p : Submodule R M` und `IsProj p f` — beides neu; Untermodul-Item + binäres Prädikat? | a |
| 54 | trace | IsIdempotentElem.trace_eq_zero_iff | Basis-Ring `R` und Modul `M`: char-null, kommutativ — neue Ring/Modul-Items oder Körper-Näherung? | a |
| 55 | trace | isNilpotent_trace_of_isNilpotent | `IsNilpotent` auf Endomorphismus (Prämisse) und Skalar (Konklusion) — ein oder zwei Untertyp-Items? | a |
| 56 | trace | trace_comp_eq_mul_of_commute_of_isNilpotent | `IsNilpotent (g - algebraMap R _ μ)` — Nilpotenz-Prädikat als Gleichung oder Untertyp im Setting? | a |
| 57 | trace | trace_baseChange | `baseChange` + `AlgebraTensorModule.map` — eigenständiger Operator oder Ableitung? | a |
| 58 | trace | Module.Free.bijective_algebraMap_of_finrank_eq_one | `S` als R-Algebra (Ring + freier Modul) — neue Items oder Körper-Näherung? | a |
| 59 | ode_transform | IsIntegralCurveOn.comp_add | `IsIntegralCurveOn(γ,v,s)`: neue Klasse mit Instance-of-Idiom oder ternäres Prädikat? | a |
| 60 | ode_transform | isIntegralCurveOn_comp_add | `I5001` bereits im Modul — Reuse oder neues Item? | a |
| 61 | ode_transform | isIntegralCurveOn_comp_sub | `comp_sub` mit `γ ∘ (· - dt)` und `dt +ᵥ s` — `I1006`/`I1007` mit negiertem Arg oder neue Items? | a |
| 62 | ode_transform | IsIntegralCurveOn.comp_sub | `I5002` bereits vorhanden — Scope-Wiederverwendung oder neues Item? | a |
| 63 | ode_transform | isIntegralCurveAt_comp_add | `IsIntegralCurveAt` (punktweise) vs. `I1004` (mengenbasiert) — gemeinsames Eltern-Item? | a |
| 64 | ode_transform | IsIntegralCurve.comp_add | Globales `IsIntegralCurve`-Prädikat (keine Domäne) — neues binäres Prädikat oder `I1005` mit `Set.univ`? | a |
| 65 | ode_transform | isIntegralCurveOn_comp_mul_ne_zero | `(a ≠ 0) → (IsCurveOn … ↔ IsCurveOn …)` — äußere IFF-Verbindung enkodieren | a |
| 66 | ode_transform | isIntegralCurve_const | Konstante Kurve `fun _ => x` + `∀t, v t x = 0` — drei neue Items oder kollabiertes Prädikat? | a |

*Alle 66 Fork-Entscheidungen wählten Option a.*

---

## D. Failure-Klassifikation

| Korpus | Theorem | Outcome | Fehlerklasse |
|--------|---------|---------|--------------|
| eigenspace | mem_genEigenspace | error | `TimeoutExpired`: Timeout nach 694,5 s (erster Claude-Aufruf abgebrochen) |
| eigenspace | mem_genEigenspace_top | error | `TimeoutExpired`: Timeout (zweiter Versuch nach Fork ebenfalls abgebrochen) |
| eigenspace | mem_genEigenspace_one | failed | `InvalidScopeNameError`: Item `I5006["genEigenspace_one"]` hat bereits eine Scope-Zuweisung |
| eigenspace | HasUnifEigenvalue.mem_spectrum | failed | `SyntaxError`: ungültiges Unicode-Zeichen `→` (U+2192) im generierten Python-Code |
| eigenspace | HasUnifEigenvalue.le | failed | `TypeError`: `I31["less-or-equal-than-relation"]` hat kein `_custom_call` (nicht aufrufbar) |
| trace | trace_transpose | failed | `SyntaxError`: ungültiges Unicode-Zeichen `∘` (U+2218) im generierten Python-Code |
| trace | IsIdempotentElem.trace_eq_zero_iff | failed | `TypeError`: Entität ist keine Klasse — kann nicht instanziiert werden |
| trace | Module.Free.bijective_algebraMap_of_finrank_eq_one | error | `TimeoutExpired`: Timeout nach 1036,4 s (längster Lauf im gesamten Run 2) |
| ode_transform | IsIntegralCurveOn.comp_sub | failed | `InvalidScopeNameError`: Item `I5002["IsIntegralCurveOn.comp_sub"]` hat bereits eine Scope-Zuweisung |

**Zusammenfassung der Fehlerklassen in Run 2:**
- `TimeoutExpired` (3): 2× eigenspace, 1× trace
- `SyntaxError` — Unicode im generierten Code (2): 1× eigenspace, 1× trace
- `TypeError` — nicht aufrufbares Item / nicht instanziierbare Entität (2): 1× eigenspace, 1× trace
- `InvalidScopeNameError` — doppelte Scope-Zuweisung (2): 1× eigenspace, 1× ode_transform

---

## E. Qualitative Beobachtungen

### (i) Key-Remap-Events: Kollidierende Theoreme jetzt erfolgreich

Der Key-Remap-Mechanismus (Commits `354862b0`, `d4cf6198`) hat die Kollisions-Kaskade vollständig
beseitigt. In Run 1 führten Index-Kollisionen (z.B. `I73` in eigenspace, `I3051` in trace) zu
Kaskaden-Fehlern, die jeweils 5–8 Folge-Theoreme blockierten. In Run 2 werden Kollisionen
automatisch durch Remapping auf freie Slots aufgelöst:

- **eigenspace**: 14 Remap-Events in 13 Theoremen. Beispiele: `genEigenspace_directed` (I5000→I5001),
  `maxUnifEigenspaceIndex_le_finrank` (5 Einträge remapped: I1033→I1045, I1034→I1046 u.a.).
  12 von 13 Theorem-Records mit Remap-Events enden mit `ok` — nur `HasUnifEigenvalue.le` schlägt
  aus einem anderen Grund fehl (TypeError). Konkret: Die Theoreme `genEigenspace_top_eq_maxUnifEigenspaceIndex`,
  `genEigenspace_le_genEigenspace_maxUnifEigenspaceIndex`, `mapsTo_genEigenspace_of_comm` u.a., die in
  Run 1 alle mit "I73 already occupied" scheiterten, liefern in Run 2 `ok`-Ergebnisse.

- **trace**: 13 Remap-Events in 13 Theoremen. Items aus dem I905x-Bereich wurden systematisch auf
  I906x–I910x umgemappt. 11 von 13 Theoreme mit Remaps enden `ok`; die beiden Ausnahmen scheitern
  an unabhängigen Fehlern (TypeError, Timeout).

- **ode_transform**: Kein einziger Remap-Event. Der Korpus nutzt einen weniger dichten Item-Namensraum,
  sodass keine Kollisionen auftraten.

### (ii) Reuse-Verhalten über Theoreme hinweg

Beide großen Korpora zeigen starkes intra-modul-Reuse: In eigenspace werden die frühzeitig erstellten
Items (`I1004["generalized eigenspace"]`, `I1005["IsIntegralCurveOn"]`, `I1015["HasUnifEigenvalue"]`,
`I1020["HasUnifEigenvector"]`) durchgängig von späteren Theoremen referenziert. In trace bauen alle
Spur-Varianten-Theoreme auf `I3001["trace operator"]` und `I3005["linear map to matrix"]` auf.
Bemerkenswert: Die Fork-Fragen in ode_transform zeigen, dass der Agent `I5001`/`I5002` (comp_add,
comp_sub) explizit als "bereits im Modul vorhanden" erkennt und Reuse wählt — dies führt in einem
Fall (`IsIntegralCurveOn.comp_sub`) zu einem InvalidScopeNameError, weil das Item keinen zweiten Scope
erhalten kann.

### (iii) Kostenverteilung: mean/max cost_usd pro Theorem, ok vs. failed

| Korpus | ok mean | ok max | failed/error mean | failed/error max |
|--------|---------|--------|-------------------|-----------------|
| eigenspace | 0,363 $ | 0,693 $ | 0,293 $ | 0,661 $ |
| trace | 0,278 $ | 0,536 $ | 0,469 $ | 0,530 $ |
| ode_transform | 0,289 $ | 0,910 $ | 0,507 $ | 0,507 $ |

`Failed`- und `error`-Theoreme sind **nicht billiger** — in trace und ode_transform sogar teurer,
da Timeouts und Retry-Versuche vor dem Scheitern Tokens verbrauchen. Der Gesamtaufwand beläuft sich
auf **28,38 $ für 89 Theoreme** (davon 80 `ok`), also ca. **0,319 $ pro Theorem** im Durchschnitt.
Das teuerste Einzeltheorem ist `IsIntegralCurveOn.comp_add` im ode_transform-Korpus mit 0,91 $.

### (iv) Neue Fehlerklassen ersetzen Kollisions-Kaskade

Die verbleibenden 9 Fehler verteilen sich auf vier qualitativ verschiedene Klassen, von denen keine
systemischer Natur ist:
- **SyntaxError** (2): der Agent generiert Lean-Symbole wie `→` oder `∘` direkt in Python-Code,
  statt ASCII-Äquivalente zu verwenden.
- **TypeError** (2): nicht aufrufbare Items (`I31`) oder nicht-instanziierbare Entitäten.
- **TimeoutExpired** (3): Theoreme mit sehr breitem Typ-Signatur-Raum (Module.Free.bijective... 1036 s)
  oder komplexen Existenz-Quantifikationen (mem_genEigenspace*).
- **InvalidScopeNameError** (2): Reuse eines bereits scope-zugewiesenen Items, anstatt ein neues zu erstellen.

Keine dieser Klassen erzeugt Kaskaden. Jeder Fehler betrifft genau ein Theorem.

### (v) ode_transform: Rückgang von 100 % auf 94,7 %

Run 1 erzielte 19/19 `ok` für ode_transform. In Run 2 scheitert `IsIntegralCurveOn.comp_sub`
(InvalidScopeNameError) — nicht weil das Theorem inhärent schwieriger wäre, sondern weil der Agent
Item `I5002` wiederverwenden wollte, das in einem Vorgänger-Theorem (`IsIntegralCurveOn.comp_add`)
bereits einen Scope erhalten hatte. Dieser Einzelfall ist ein State-Management-Artifact, kein
strukturelles Problem des Korpus.
