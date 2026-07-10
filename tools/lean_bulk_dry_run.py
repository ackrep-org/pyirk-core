"""Mocked bulk dry-run for ``pyirk --import-lean ... --all``.

Drives the full CLI --all path over a real ``.lean`` file with
``propose_via_claude`` replaced by a deterministic mock, so the *mechanics*
(parse → retrieval → append → round-trip validation → next theorem) can be
exercised at scale without spending tokens. Intended as a cheap pre-flight
before a real (token-spending) bulk run on the VPS.

Optionally injects failures to exercise the rollback/retry and FORK paths:

    python tools/lean_bulk_dry_run.py CORPUS.lean
    python tools/lean_bulk_dry_run.py CORPUS.lean --fail-every 5 --fork-every 7

Exit code 0 iff all theorems imported successfully.
"""

import argparse
import os
import re
import sys
import tempfile
import time

# make the surrounding worktree's src/ win over any editable install
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC_DIR)

from pyirk import authoring, script  # noqa: E402
from pyirk.authoring import lean  # noqa: E402

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OCSE = os.path.join(os.path.dirname(THIS_DIR), "tests", "test_data", "ocse_subset", "math1.py")

_SOURCE_INFO_RE = re.compile(r"Lean / mathlib4: (\S+)")

OK_TEMPLATE = """\
OK:
```python
I{key} = p.create_item(
    R1__has_label="{label}",
    R2__has_description="mock import of {label}",
    R4__is_instance_of=p.I15["implication proposition"],
    R9999__has_source_reference="Lean / mathlib4: {label}",
)
```
"""

# OK block that declares the well-known builtin key I17, guaranteed to be in
# the occupied set -> triggers remap_colliding_keys without causing a retry
COLLIDE_TEMPLATE = """\
OK:
```python
I17 = p.create_item(
    R1__has_label="{label}",
    R2__has_description="mock import of {label}",
    R4__is_instance_of=p.I15["implication proposition"],
    R9999__has_source_reference="Lean / mathlib4: {label}",
)
```
"""

# syntactically fine, but references an undefined name -> fails round-trip
# validation and forces the rollback + re-prompt path
BROKEN_TEMPLATE = """\
OK:
```python
I{key} = p.create_item(
    R1__has_label="{label} broken",
    R2__has_description="deliberately references an undefined item",
    R4__is_instance_of=THIS_NAME_DOES_NOT_EXIST,
)
```
"""

FORK_TEMPLATE = """\
FORK:
Q: mock fork: should '{label}' be encoded as (a) or (b)?
(a) first mock option
(b) second mock option
"""


class MockClaude:
    """Deterministic stand-in for ``propose_via_claude``.

    State machine keyed on prompt content: a prompt containing the
    retry/fork marker strings injected by ``import_one_statement`` is a
    follow-up call and always gets a valid OK block; otherwise it is the
    first attempt for a new theorem and may get an injected failure/FORK.
    """

    def __init__(self, fail_every: int = 0, fork_every: int = 0, collide_every: int = 0):
        self.fail_every = fail_every
        self.fork_every = fork_every
        self.collide_every = collide_every
        self.calls = 0
        self.theorem_idx = 0  # 1-based, counted on first attempts only
        self.item_key = 8001
        self.stats = {"ok": 0, "injected_fail": 0, "injected_fork": 0, "injected_collide": 0, "followup": 0}

    #: fixed per-call price so the dry run also exercises cost aggregation
    MOCK_COST_USD = 0.001

    def __call__(self, prompt: str, timeout: int = 600, model: str = "sonnet"):
        return authoring.ClaudeCallResult(text=self._respond(prompt), cost_usd=self.MOCK_COST_USD)

    def _respond(self, prompt: str) -> str:
        self.calls += 1
        m = _SOURCE_INFO_RE.search(prompt)
        label = m.group(1) if m else f"unknown_{self.calls}"

        is_followup = (
            "failed validation" in prompt
            or "User resolved a previous modeling fork" in prompt
            or "malformed" in prompt
        )
        if not is_followup:
            self.theorem_idx += 1
            if self.fork_every and self.theorem_idx % self.fork_every == 0:
                self.stats["injected_fork"] += 1
                return FORK_TEMPLATE.format(label=label)
            if self.fail_every and self.theorem_idx % self.fail_every == 0:
                self.stats["injected_fail"] += 1
                key = self.item_key
                self.item_key += 1
                return BROKEN_TEMPLATE.format(key=key, label=label)
            if self.collide_every and self.theorem_idx % self.collide_every == 0:
                self.stats["injected_collide"] += 1
                return COLLIDE_TEMPLATE.format(label=label)
        else:
            self.stats["followup"] += 1

        self.stats["ok"] += 1
        key = self.item_key
        self.item_key += 1
        return OK_TEMPLATE.format(key=key, label=label)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lean_file", help="path or URL of the .lean corpus")
    ap.add_argument("--ocse-path", default=DEFAULT_OCSE)
    ap.add_argument(
        "--fail-every",
        type=int,
        default=0,
        metavar="N",
        help="every N-th theorem first gets a block that fails validation",
    )
    ap.add_argument(
        "--fork-every", type=int, default=0, metavar="M", help="every M-th theorem first gets a FORK response"
    )
    ap.add_argument(
        "--collide-every",
        type=int,
        default=0,
        metavar="N",
        help="every N-th theorem proposes a block declaring builtin key I17 "
        "to exercise the remap_colliding_keys path",
    )
    ap.add_argument("--limit", type=int, default=0, help="only import the first LIMIT theorems (0 = all)")
    cli = ap.parse_args()

    source = lean.fetch_lean_source(cli.lean_file)
    theorems = lean.parse_theorems(source)
    print(f"corpus: {cli.lean_file} -> {len(theorems)} theorems parsed")
    if cli.limit:
        # truncate the corpus by rewriting a temp file is overkill; instead we
        # monkeypatch parse_theorems to return the head slice
        head = theorems[: cli.limit]
        lean.parse_theorems = lambda _src, _head=head: list(_head)
        print(f"limiting to first {cli.limit} theorems")

    tmpdir = tempfile.mkdtemp(prefix="pyirk_lean_dry_run_")
    target_path = os.path.join(tmpdir, "lean_dry_run_module.py")
    stats_path = os.path.join(tmpdir, "stats.jsonl")

    mock = MockClaude(fail_every=cli.fail_every, fork_every=cli.fork_every, collide_every=cli.collide_every)
    authoring.propose_via_claude = mock

    args = argparse.Namespace(
        import_lean=cli.lean_file,
        target=target_path,
        theorem=None,
        all_theorems=True,
        ocse_uri=None,
        ocse_path=cli.ocse_path,
        working_uri="irk:/lean_dry_run/0.1",
        source_url=None,
        # exercise the unattended-bulk-run configuration (same as the VPS run)
        fork_policy="first",
        stats_jsonl=stats_path,
        keep_going=True,
    )

    t0 = time.time()
    rc = script.import_lean(args)
    dt = time.time() - t0

    with open(target_path) as fp:
        written = fp.read()
    n_items = len(re.findall(r"^I\d+ = p\.create_item", written, re.MULTILINE))

    print()
    print("=" * 60)
    print(f"exit code:            {rc}")
    print(f"wall time:            {dt:.1f} s")
    print(f"propose calls:        {mock.calls}")
    print(f"  first attempts:     {mock.theorem_idx}")
    print(f"  follow-up calls:    {mock.stats['followup']}")
    print(f"  injected failures:  {mock.stats['injected_fail']}")
    print(f"  injected forks:     {mock.stats['injected_fork']}")
    print(f"  injected collisions:{mock.stats['injected_collide']}")
    print(f"items in module:      {n_items}")
    print(f"working module:       {target_path}")

    # cross-check the structured stats stream against the mock's own counters
    import json

    with open(stats_path) as fp:
        records = [json.loads(line) for line in fp if line.strip()]
    n_ok = sum(1 for r in records if r["outcome"] == "ok")
    n_forks = sum(r["n_forks"] for r in records)
    n_vfails = sum(r["n_validation_fails"] for r in records)
    n_remaps = sum(r.get("n_key_remaps", 0) for r in records)
    n_calls = sum(r["n_claude_calls"] for r in records)
    cost = sum(r["cost_usd"] or 0 for r in records)
    print(
        f"stats records:        {len(records)} (ok={n_ok}, forks={n_forks}, vfails={n_vfails}, remaps={n_remaps})"
    )
    print(f"claude calls (stats): {n_calls}, cost: ${cost:.4f}")
    print(f"stats file:           {stats_path}")

    if cli.collide_every:
        expected_remaps = mock.stats["injected_collide"]
        remap_label = "PASS" if n_remaps == expected_remaps else "FAIL"
        print(
            f"key-remap cross-check: {remap_label} -- expected {expected_remaps} remap(s), observed {n_remaps}"
        )

    expected = cli.limit or len(theorems)
    stats_consistent = (
        len(records) == expected
        and n_forks == mock.stats["injected_fork"]
        and n_vfails == mock.stats["injected_fail"]
        and n_remaps == mock.stats["injected_collide"]
        # every mock call must be accounted for, with its price
        and n_calls == mock.calls
        and abs(cost - mock.calls * MockClaude.MOCK_COST_USD) < 1e-9
    )
    if rc == 0 and n_items == expected and stats_consistent:
        print(f"RESULT: OK -- all {expected} theorems imported, stats consistent")
        return 0
    print(
        f"RESULT: MISMATCH -- expected {expected} items, got {n_items}, rc={rc}, "
        f"stats_consistent={stats_consistent}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
