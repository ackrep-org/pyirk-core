(sec_howto_nemo_delegation)=
# Nemo delegation (optional rule-engine acceleration)

## Overview

Pyirk's rule engine can optionally delegate the evaluation of a curated subset
of hot-spot rules to the Nemo datalog engine via its `nmo` CLI. The pyirk
side exports the relevant facts and rules,
invokes `nmo` as a subprocess, ingests the result CSV, and materializes the
new triples back into the native `DataStore`. The native Python engine
remains the authoritative reference: delegation is an opt-in performance
shortcut, never a replacement.

The measured payoff on the H5 phase-2 workload (OCSE control-theory rules)
is **~175x speedup** of the rule-evaluation phase (`t_native=320.93 s` →
`t_delegation=1.83 s`, see
[`docs/design/h5_phase2_report.md`](../../design/h5_phase2_report.md)).
On the smaller H5 extension workload the speedup is more modest at ~1.35x
(`t_native=1.49 s` → `t_delegation=1.10 s`,
[`docs/design/h5_extension_report.md`](../../design/h5_extension_report.md)).

**Defaults: delegation is OFF.** No upstream user is affected unless they
explicitly opt in via the environment variable below.

## Installation of `nmo`

The validated upstream version is **Nemo 0.10.x**. Other versions may work
but are not part of the acceptance gate (see *Known limits* below).
For installation instructions please see the upstream Nemo project; pyirk
does **not** bundle or vendor the `nmo` binary.

## Environment variables

Two environment variables control the feature; both are read fresh at every
rule-engine entry point.

* `PYIRK_NEMO_DELEGATION=1` — enables the delegation path. Any other value
  (or absence) keeps the native Python engine in charge.
* `PYIRK_NEMO_BIN=/abs/path/to/nmo` — optional override that pins the
  `nmo` binary used by pyirk. Useful for CI, container images, or when
  multiple Nemo versions co-exist on a developer machine.

### Resolver order

When delegation is enabled, the binary is resolved in the following
deterministic order. The first existing candidate wins.

1. `PYIRK_NEMO_BIN` — if set *and* the path exists.
2. `shutil.which("nmo")` — first hit on `PATH`.
3. `/home/user/bin/nmo` — legacy host default, if it exists.
4. None — no binary available; delegation falls back to the native engine.

Exactly one `logger.info` line per process documents which source was
picked (e.g. `nmo binary resolved via shutil.which: /usr/local/bin/nmo`).
This makes the active path auditable from log output alone, without
requiring a full debug session.

## Delegated rule categories

The precise list of delegatable rules differs per phase and is maintained
in the design reports rather than duplicated here:

* H5 phase 2 (OCSE control-theory hot-spot rules): see
  [`docs/design/h5_phase2_report.md`](../../design/h5_phase2_report.md).
* H5 extension (literal-premise rules I705/I790/I800/I820): see
  [`docs/design/h5_extension_report.md`](../../design/h5_extension_report.md).

All other rules continue to execute through the native Python engine; the
split is decided per rule, not per call.

## Known limits

* **Qualifiers are deferred.** Rules whose premises or conclusions rely on
  qualifier propagation are not delegated; the delegation hook treats
  qualifier work as a no-op.
* **V4 fixpoint loop is not delegated.** The outer fixpoint iteration
  remains in Python — Nemo is invoked per round, not in place of the
  iteration.
* **Major version mismatch of `nmo` triggers a fallback.** If
  `nmo --version` reports a major version different from the validated
  `0.10.x` series, pyirk emits one warning and falls back to the native
  engine. Major bumps reliably break the RLS codegen/CLI contract.
* **Minor mismatch warns and still tries.** A `0.11.z` (or similar)
  binary is attempted with a single warning, because 0.x minor releases
  upstream are usually additive; a downstream protocol mismatch is caught
  by the runtime hook and falls back automatically.

## Behavior without binary / on failure

The delegation hook is built to fail safely. There are exactly three
error modes, and each emits **at most one `logger.warning` per process**
(per error mode), then yields to the native engine:

1. **No `nmo` binary located** — none of the resolver candidates point to
   an existing file. One warning, native fallback.
2. **Version mismatch (major or unparseable)** — one warning, native
   fallback. Minor mismatch warns once and proceeds.
3. **Subprocess failure or unparseable CSV output** — one warning,
   native fallback. The hook signals failure *before* the
   `DataStore`-mutating `_materialize_tuples` stage runs, so the store
   is never left with half-written statements.

The idempotent warning policy keeps long-running rule-engine sessions
quiet: a broken setup produces one diagnostic line per error class, not
one per rule batch.
