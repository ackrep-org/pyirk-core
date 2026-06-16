# Bulk-Run Summary: Three Lean-Import Corpora

Generated from stats files in `bulk_runs/{eigenspace,trace,ode_transform}/stats.jsonl`.
De-duplication: first record per `(namespace, theorem)`.

---

## A. Per-Corpus Metrics

| Corpus | Total | ok | failed | error | Fork rate | Val-retry rate | Mean dur (s) | Max dur (s) |
|--------|-------|----|--------|-------|-----------|----------------|--------------|-------------|
| eigenspace | 35 | 20 | 14 | 1 | 80.0 % (28/35) | 60.0 % (21/35) | 315.9 | 792.6 |
| trace | 35 | 27 | 8 | 0 | 68.6 % (24/35) | 34.3 % (12/35) | 229.5 | 793.6 |
| ode_transform | 19 | 19 | 0 | 0 | 31.6 % (6/19) | 10.5 % (2/19) | 180.9 | 394.1 |

- **Fork rate**: fraction of unique theorems with at least one `fork` event.
- **Val-retry rate**: fraction with at least one `validation_fail` event.

---

## B. Fork Questions

All fork events from first-occurrence records.

| # | Corpus | Theorem | Question (abbreviated) | Chosen |
|---|--------|---------|------------------------|--------|
| 1 | eigenspace | mem_genEigenspace | Existential `∃ l ≤ k, x ∈ ker((f−μ•1)^l)` — no native binder in `new_equation`. Which encoding? | a |
| 2 | eigenspace | genEigenspace_directed | `Directed (· ≤ ·)` predicate on submodule family — no match in index. How to represent? | a |
| 3 | eigenspace | mem_genEigenspace_nat | Both iff sides are set-membership `x ∈ S`; `new_equation` needs expression equality. How? | a |
| 4 | eigenspace | mem_genEigenspace_top | Same — both sides are set-membership propositions. How to encode the biconditional? | a |
| 5 | eigenspace | genEigenspace_eq_iSup_genEigenspace_nat | RHS `⨆ l : {l : ℕ // l ≤ k}` — how to encode bounded-index supremum? | a |
| 6 | eigenspace | genEigenspace_top | How does `I10` relate to the unbounded `⨆ k : ℕ`? Arity-2 reuse or new item? | a |
| 7 | eigenspace | genEigenspace_one | Unconditional equality — no logical premise exists. How to structure setting/premise/assertion? | a |
| 8 | eigenspace | mem_genEigenspace_zero | `0 : M` (module zero) — reuse `ma.I5000["scalar zero"]` or new module-zero item? | a |
| 9 | eigenspace | genEigenspace_zero | `⊥` (trivial submodule) — new named constant vs. structural `ker(id)` vs. scalar zero proxy? | a |
| 10 | eigenspace | UnifEigenvalues.mk_val | `⟨μ.val, μ.property⟩ = μ` requires subtype constructor; proof term not representable. How? | a |
| 11 | eigenspace | HasUnifEigenvector.hasUnifEigenvalue | `HasUnifEigenvector(f,μ,k,x)` is 4-ary; pyirk tops out at arity 3. How to encode? | a |
| 12 | eigenspace | HasUnifEigenvector.apply_eq_smul | Type of `x : M` in setting — `ma.I7151["vector"]` vs. new "module element" item? | a |
| 13 | eigenspace | HasUnifEigenvector.pow_apply | `n : ℕ` (plain nat) vs. `I3["extended natural number"]` (ℕ∞). New subclass or reuse? | a |
| 14 | eigenspace | HasUnifEigenvalue.exists_hasUnifEigenvector | `∃ v, HasUnifEigenvector μ k v` — how to encode existential in assertion scope? | a |
| 15 | eigenspace | HasUnifEigenvalue.isNilpotent_of_isNilpotent | `IsNilpotent` appears on both endomorphism and scalar — one abstract predicate or two typed items? | a |
| 16 | eigenspace | HasUnifEigenvalue.mem_spectrum | `μ ∈ spectrum R f` — spectrum not in index. Set-valued operator + membership, or binary predicate? | a |
| 17 | eigenspace | genEigenspace_div | `a / b` as eigenvalue — no scalar division in module. New binary operator? | a |
| 18 | eigenspace | genEigenrange_nat | Two new operators analogous to existing kernel/eigenspace — standalone or shared parent type? | a |
| 19 | eigenspace | HasUnifEigenvalue.exp_ne_zero | `k ≠ 0` — disequality, not equation. New `is_nonzero` predicate or `not_equal` operator? | a |
| 20 | eigenspace | genEigenspace_top_eq_maxUnifEigenspaceIndex | `[IsNoetherian R M]` typeclass — subtype in setting or boolean predicate in premise? | a |
| 21 | eigenspace | genEigenspace_top_eq_maxUnifEigenspaceIndex | (retry) Same Noetherian constraint — two new items or one boolean predicate? | a |
| 22 | eigenspace | genEigenspace_le_genEigenspace_maxUnifEigenspaceIndex | Submodule-ordering assertion `≤` — new `I_sle` operator or relation? | a |
| 23 | eigenspace | genEigenspace_eq_genEigenspace_maxUnifEigenspaceIndex_of_le | Premise is `maxUnifEigenspaceIndex ≤ k`. New `leq` + `maxUnifEigenspaceIndex` operators? | a |
| 24 | eigenspace | HasUnifEigenvalue.lt | `0 < m` — new "positive extended natural" subtype or explicit `<` predicate in premise? | a |
| 25 | eigenspace | hasUnifEigenvalue_iff_hasUnifEigenvalue_one | `hk : 0 < k ⊢ … ↔ …` — positivity side condition + iff. Use subtype for k or two-equation premise? | a |
| 26 | eigenspace | maxUnifEigenspaceIndex_le_finrank | Inequality conclusion `≤ finrank K V`. New `leq_nat` boolean operator? | a |
| 27 | eigenspace | genEigenspace_le_genEigenspace_finrank | Submodule containment `≤`. New relation `R_is_submodule_of` or boolean operator? | a |
| 28 | eigenspace | genEigenspace_eq_genEigenspace_finrank_of_le | `finrank K V` as callable expression — new unary "finite rank" operator? | a |
| 29 | eigenspace | genEigenspace_eq_genEigenspace_finrank_of_le | (retry) `finrank K V` — unary operator on endomorphism vs. explicit dimension variable? | a |
| 30 | eigenspace | mapsTo_genEigenspace_of_comm | `Commute f g` (premise) + `MapsTo g S S` (assertion) — composition equation or boolean predicates? | a |
| 31 | eigenspace | mapsTo_genEigenspace_of_comm | (retry) `MapsTo g S S` — general ternary predicate or binary `is_invariant_under`? | a |
| 32 | trace | traceAux_def | `Matrix.trace` — bare unary operator or share parent type with `ma.I5359["determinant"]`? | a |
| 33 | trace | traceAux_eq | Functional equality `traceAux R b = traceAux R c`. Expand pointwise (∀ f) or treat as function-object? | a |
| 34 | trace | trace_eq_matrix_trace_of_finset | `LinearMap.trace` (distinct from traceAux) — new item `I3009` or reuse traceAux? | a |
| 35 | trace | trace_eq_matrix_trace | `I3005["linear map to matrix"]` — arity 2 or arity 3 (two basis args)? | a |
| 36 | trace | trace_mul_comm | `f * g` (composition) — new `I3012` item or use pyirk's overloaded `*`? | a |
| 37 | trace | trace_lie_mul_eq | Lie bracket `⁅f,g⁆` — domain-specific or abstract Lie algebra item? | a |
| 38 | trace | trace_conj | `f : (M →ₗ M)ˣ` invertible endomorphism — new subtype item + inverse operator? | a |
| 39 | trace | trace_eq_contract_of_basis | `dualTensorHom` and `contractLeft` — minimal untyped, full type hierarchy, or domain-only? | a |
| 40 | trace | trace_eq_contract_of_basis' | `dualTensorHomEquivOfBasis` — new standalone item or specialisation of existing `I3022`? | a |
| 41 | trace | trace_eq_contract | Function equality `trace ∘ₗ dualTensorHom = contractLeft` — new compose operator or pointwise? | a |
| 42 | trace | trace_eq_contract' | Unapplied map equality with `dualTensorHomEquiv` (not `dualTensorHom`) — how to encode? | a |
| 43 | trace | trace_one | Ring `R` and module `M` typing — new "commutative ring"/"R-module" items or narrow to field? | a |
| 44 | trace | trace_id | Unconditional `trace(id) = finrank` — `p.I15` with premise constraints or bare proposition? | a |
| 45 | trace | trace_transpose | Function-level equality `trace_dual ∘ transpose = trace_M` — new transpose item, pointwise encoding? | a |
| 46 | trace | trace_prodMap | `prodMapLinear`, `prodMap`, `coprod id id` — 4 new items, 2 items, or 1 + opaque? | a |
| 47 | trace | trace_tensorProduct | `trace(f⊗g) = trace(f)·trace(g)` via `compr₂`/`compl₁₂`/`mapBilinear`/`lsmul` — literal structure or semantic shortcut? | a |
| 48 | trace | trace_comp_comm | `f : M →ₗ N`, `g : N →ₗ M` (non-endo) — new "linear map between modules" type or reuse endomorphism? | a |
| 49 | trace | trace_conj' | `e : M ≃ₗ N` (cross-module isomorphism) — new "linear isomorphism between modules" supertype? | a |
| 50 | trace | IsProj.trace | `IsProj p f` projection condition — new "submodule" item + binary predicate, or bake into `f` type? | a |
| 51 | trace | IsIdempotentElem.trace_eq_zero_iff | Char-zero comm ring + idempotency — new ring/module items or approximate with field? | a |
| 52 | trace | isNilpotent_trace_of_isNilpotent | `IsNilpotent` on endomorphism (premise) and scalar (assertion) — two subtype items or one predicate? | a |
| 53 | trace | trace_comp_eq_mul_of_commute_of_isNilpotent | `IsNilpotent(g − μ·id)` in premise — predicate-as-equation or nilpotent-subtype in setting? | a |
| 54 | trace | trace_baseChange | `f.baseChange A` — new standalone binary operator, or derive from `I3041["tensor product of linear maps"]`? | a |
| 55 | trace | Module.Free.bijective_algebraMap_of_finrank_eq_one | `Function.Bijective (algebraMap R S)` — boolean predicate item or bijective-hom subtype? | a |
| 56 | ode_transform | IsIntegralCurveOn.comp_add | `IsIntegralCurveOn(γ,v,s)` — new class with instance-of idiom, or ternary predicate returning truth? | a |
| 57 | ode_transform | isIntegralCurveOn_comp_sub | Sub-variant operators: reuse I1006/I1007 with negated arg, or new `I1008`/`I1009`? | a |
| 58 | ode_transform | isIntegralCurveAt_comp_add | `t₀ - dt` in setting — use `st.t0 - st.dt` directly or new `vadd neg on real point` item? | a |
| 59 | ode_transform | IsIntegralCurve.comp_add | `IsIntegralCurve γ v` (no domain) — new binary predicate `I1013` or reuse `I1005` with `Set.univ`? | a |
| 60 | ode_transform | IsIntegralCurveOn.comp_mul | `a • v ∘ (· * a)` scaling + precomposition — two new operator items or one combined? | a |
| 61 | ode_transform | isIntegralCurve_const | Constant curve + `∀t, v t x = 0` — three new items (curve, eval, zero-vector) or collapsed predicate? | a |

---

## C. Failure Classification

| Corpus | Theorem | Outcome | Apparent error class |
|--------|---------|---------|----------------------|
| eigenspace | genEigenspace_directed | failed | `ValueError`: label mismatch (`'proposition'` used as scope label instead of `'scope'`) |
| eigenspace | mem_genEigenspace_nat | failed | `TypeError`: `I5["iterated-kernel existential formula"]` not callable (no `_custom_call`) |
| eigenspace | mem_genEigenspace_top | error | `TypeError`: same — `I5` not callable; combined with timeout on attempt 2 |
| eigenspace | mem_genEigenspace_zero | failed | `TypeError`: evaluated-mapping item `Ia98516` not callable |
| eigenspace | genEigenspace_zero | failed | `AssertionError`: item index `I17` already occupied (index collision) |
| eigenspace | genEigenspace_div | failed | `SyntaxError`: Unicode bullet `•` (U+2022) in generated Python |
| eigenspace | genEigenspace_top_eq_maxUnifEigenspaceIndex | failed | `AssertionError`: item `I73` already occupied (index collision cascade) |
| eigenspace | genEigenspace_eq_genEigenspace_maxUnifEigenspaceIndex_of_le | failed | `AssertionError`: `I73` already occupied |
| eigenspace | HasUnifEigenvalue.le | failed | `TypeError`: `I31["less-or-equal-than-relation"]` not callable |
| eigenspace | HasUnifEigenvalue.lt | failed | `AssertionError`: `I73` already occupied |
| eigenspace | hasUnifEigenvalue_iff_hasUnifEigenvalue_one | failed | `AssertionError`: `I80` already occupied |
| eigenspace | maxUnifEigenspaceIndex_le_finrank | failed | `AssertionError`: `I73` already occupied |
| eigenspace | genEigenspace_le_genEigenspace_finrank | failed | `AssertionError`: `I73` already occupied |
| eigenspace | genEigenspace_eq_genEigenspace_finrank_of_le | failed | `AssertionError`: `I73` already occupied |
| eigenspace | mapsTo_genEigenspace_of_comm | failed | `AssertionError`: `I73` already occupied |
| trace | trace_eq_contract_of_basis' | failed | `TypeError`: evaluated mapping for `dualTensorHomEquivOfBasis(b)` not callable |
| trace | trace_id | failed | `TypeError`: `I3031["identity linear endomorphism"]` not a class (cannot be instantiated) |
| trace | trace_conj' | failed | `AssertionError`: `I3051` already occupied (index collision cascade) |
| trace | IsProj.trace | failed | `AssertionError`: `I3051` already occupied |
| trace | IsIdempotentElem.trace_eq_zero_iff | failed | `AssertionError`: `I3051` already occupied |
| trace | trace_comp_eq_mul_of_commute_of_isNilpotent | failed | `AssertionError`: `I3051` already occupied |
| trace | trace_baseChange | failed | `AssertionError`: `I3051` already occupied |
| trace | Module.Free.bijective_algebraMap_of_finrank_eq_one | failed | `AssertionError`: `I3060` already occupied (same cascade) |

**ode_transform**: no failures.

---

## D. Qualitative Observations

- **Strong intra-module reuse.** Later theorems consistently reference items created by earlier ones.
  In `lean_eigenspace.py` the ternary operator `I4["generalized eigenspace operator"]`, unary
  `I7["linear map kernel"]`, constant `I8["identity endomorphism"]`, and accumulating index-set /
  supremum items (I10, I12, I14, I19, …) are reused across many subsequent theorem items.  In
  `lean_ode_transform.py` the predicates `I1005["IsIntegralCurveOn"]`, `I1010["IsIntegralCurveAt"]`,
  and operators `I1006`/`I1008`/`I1014`/`I1015` carry through every comp-variant theorem.

- **ode_transform: separate operators per variant, not merged structure.**
  Despite `comp_add`, `comp_sub`, `comp_mul`, and `comp_neg` all being shifts of the same integral-
  curve predicate, the LLM did **not** create a single parameterised "composition transform" operator.
  It introduced a distinct pair of operators per arithmetic operation
  (e.g. `I1006`/`I1007` for add, `I1008`/`I1009` for sub, `I1014`/`I1015`/`I1016` for mul).  The
  shared predicate `I1005["IsIntegralCurveOn"]` is reused everywhere, but the transformation
  operators themselves are not merged.

- **Dominant failure mode: index collision cascade.**
  In both eigenspace and trace, a single early theorem attempt that chose (but then collided on) a
  specific item number (e.g. `I73` in eigenspace, `I3051` in trace) causes all subsequent theorems
  that independently try to create a new item at the same index to fail immediately with
  `AssertionError: … already occupied`.  This is a cumulative-state artifact: once a partial
  (failed) run occupies slot N, every retry and all later theorems that also want slot N are blocked.

- **Surprising outcome-rate gap across corpora.** ode_transform achieved 100 % success (19/19 ok)
  with low fork and validation-fail rates (32 % / 11 %).  The eigenspace corpus had only 57 % success
  with 80 % fork rate and 60 % validation-fail rate.  The structural difference is that ODE-transform
  theorems share a single repeated pattern (`IsIntegralCurveOn/At/curve`, precompose, shift), whereas
  eigenspace theorems involve increasingly exotic type-class constraints (Noetherian, nilpotent,
  disequalities, lattice bottoms) for which pyirk has no direct encoding primitive.

- **Duration outliers at timeout boundary.** Both eigenspace and trace contain records with
  `duration_s` close to 792–793 s, flagged as `TimeoutExpired` errors.  These represent theorems
  where the LLM ran out of time mid-attempt (apparently after a fork decision triggered a more
  complex encoding path), while all ode_transform theorems finished well under 400 s.  The timeout
  boundary appears to be approximately 800 s.
