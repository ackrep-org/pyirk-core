# pyirk and LLMs: complementary roles

A natural question when encountering pyirk is: large language models can already
read engineering documents, summarise them, answer questions about them, and
generate plausible code in any target language. Why invest in *formal* knowledge
representation at all? Why not just use an LLM?

This page argues that pyirk and LLM-based tools are not competing solutions to
the same problem. They address different needs, and combining them is more
effective than either alone. The argument has three parts: where LLMs alone are
sufficient; where they are demonstrably not; and how pyirk and LLM-based tooling
combine in practice.

## Where LLMs alone are sufficient

A substantial portion of everyday engineering and scientific work is well served
by LLMs without any formal representation underneath. Examples include

- exploratory design ("what are some approaches to X?"),
- one-off code generation,
- translation between informal descriptions,
- entry-level tutoring on textbook material,
- fast iteration in uncritical contexts.

Formal representation is overhead for this kind of work, and pyirk does not aim
to replace it. If a task is conversational, creative, and tolerates occasional
errors, an LLM is the appropriate tool.

## Where LLMs alone are not sufficient

The case for formal knowledge representation rests on classes of tasks where
LLMs are unreliable not because they lack capability, but because their output
has properties that disqualify it from specific uses. Five such classes are
discussed below.

### 1. Verifiability for certification

Safety-critical engineering domains operate under regulatory frameworks that
require formal, auditable arguments for design decisions. Examples include

- **DO-178C** (avionics software),
- **ISO 26262** (functional safety in road vehicles),
- **IEC 61508** (general functional safety) and **IEC 61511** (process industry),
- **ISO 13849** (safety of machinery),
- **IEC 62304** (medical device software).

"The language model said this design is sound" is not an admissible
justification under any of these frameworks. A formally represented knowledge
base whose statements can be traced to sources, checked for consistency, and
audited by independent reviewers is qualitatively different from an LLM
response. This is not a speculative future requirement; it is the regulatory
status quo today.

### 2. Determinism and reproducibility over decades

Engineering artefacts — plants, control systems, aircraft, embedded firmware —
exist for twenty to fifty years. The justification for their design must remain
accessible for at least that long. A conversation with a 2026 LLM is not
retrievable in 2046; a version-controlled pyirk module with stable URIs is. For
asset owners, regulators, and future maintainers this matters in practice, not
only in principle.

### 3. Mechanical composition at scale

Engineering reasoning often takes the form: *system S satisfies property P by
construction; theorem T applies to every system with property P; therefore T
applies to S.* In a formal knowledge base this is a mechanical lookup with
known correctness guarantees. In an LLM it is a generation step with unknown
error rate, which compounds over long reasoning chains.

When a design tool needs to perform thousands of such lookups against a body of
ten thousand or more engineering rules, formal lookup is quantitatively
superior (speed, completeness, auditability) and qualitatively unavailable from
LLMs (no guarantee of correctness).

### 4. Inconsistency detection across sources

Engineering standards bodies often describe overlapping concepts in
incompatible ways: ISO, IEC, and IEEE definitions of common terms can disagree
in subtle but consequential ways. A formal knowledge base into which multiple
sources have been mapped can detect such inconsistencies mechanically. An LLM,
even one trained on all relevant standards, has no mechanism to *flag*
contradictions across its training data; it tends to interpolate plausibly.

### 5. High-volume querying

A specific class of tool — embedded design assistants, code linters with
semantic awareness, automated requirement traceability checkers — issues
hundreds or thousands of knowledge-base queries per design iteration. Doing
this through LLM calls is infeasible on grounds of cost, latency, and variance.
Formal lookup is microseconds and predictable.

## The strongest single argument

Of these five, *verifiability for certification* (1) is the argument that is
genuinely watertight. The others are reinforcing — important in practice, but
with workarounds available in some settings. A reader who takes away only one
point from this page should take away the certification case; it is the one
that holds up under any honest scrutiny.

## Complementarity, not competition

A reasonable next observation is that *building* a formal knowledge base by
hand is itself enormously expensive — which is exactly why so few exist for
engineering domains. This is where LLMs return to the picture, not as an
alternative to pyirk but as the tool that makes formal representation
practical to construct in the first place.

pyirk ships a subpackage, [`pyirk.authoring`](authoring), that pairs LLM-based
ingestion with formal round-trip validation.
The LLM performs the fuzzy step: reading informal or semi-formal source
material — a Lean theorem statement, a textbook passage, a standards document —
and proposing a pyirk encoding that reuses existing entities wherever possible.
The validation loop performs the precise step: round-trip-loading the proposed
module via `irkloader`, running consistency checks, and surfacing structured
error feedback so the LLM can correct itself on the next iteration.

Neither side suffices alone. An LLM without a validation substrate produces
fluent hallucinations; formal representation without LLM-assisted ingestion is
too labour-intensive to be practical at scale.

The same pattern scales up to the intended downstream use. An engineer works
with an LLM for the fuzzy, fast, creative parts of design and analysis. For any
decision that must enter a certified, audited, or long-horizon path, the same
engineer (or a downstream tool) issues a lookup against the formal knowledge
base. The lookup either confirms the decision with traceable references to
source theorems and definitions, or returns "no formal backing — separate
verification required." This is a sensible engineering workflow architecture,
not a knowledge-representation purist's exercise.

## Summary

LLMs are well-suited to a wide range of engineering tasks and pyirk does not
aim to replace them in those tasks. pyirk targets a complementary class of
tasks — those requiring verifiability, determinism, mechanical composition,
inconsistency detection across sources, or high-volume querying — and uses
LLMs to make the underlying representation practical to construct. The two are
intended to work together, not to compete.
