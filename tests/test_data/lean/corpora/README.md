# Pinned mathlib4 bulk-run corpora

Source corpora for the lean-roadmap point-5 bulk import runs (second-corpus
replication of the findings in `pyirk-orchestrator-findings.md`). Pinned
copies, NOT fetched at run time, so the exact source state is reproducible.

Provenance:

* upstream: https://github.com/leanprover-community/mathlib4
* commit: `2d6cb2a1db02cb343c3bcb26505af89c8c597ebd` (master, fetched 2026-06-03)
* license: Apache 2.0 (see the copyright header in each file)

| file | upstream path | declarations | planned use |
|---|---|---|---|
| `LinearAlgebra_Eigenspace_Basic.lean` | `Mathlib/LinearAlgebra/Eigenspace/Basic.lean` | 94 (use `--limit 35`) | run (a): eigenvalues -- primary second corpus |
| `LinearAlgebra_Trace.lean` | `Mathlib/LinearAlgebra/Trace.lean` | 35 | run (b) |
| `Analysis_ODE_Transform.lean` | `Mathlib/Analysis/ODE/Transform.lean` | 19 | run (c): highly repetitive -- merging stressor (finding 1c) |

The first corpus (`Mathlib/Geometry/Euclidean/Angle/Unoriented/RightAngle.lean`)
was used unpinned from master in the 2026-05/06 pilot sessions; see
`irk-data/lean_theorems/README.md`.
