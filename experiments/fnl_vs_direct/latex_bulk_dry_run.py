"""Tokenfree mock dry-run for the LaTeX -> pyirk path of the FNL-vs-direct experiment.

Drives the LaTeX adapter's *segmentation* layer over the gold corpora in
``corpus_gold__gitignore__/`` and replaces the LLM round-trip with a
deterministic ``MockClaude`` that synthesises plausible event-records
without ever calling out to an API. The goal is to exercise the per-snippet
metrics pipeline (event aggregation, retry/fail bookkeeping, per-type
breakdown) at scale without spending tokens, *not* to validate generated
pyirk code.

Output: one JSONL record per snippet in ``stats.jsonl`` plus a roll-up
``summary.json``. Default out-dir is ``experiments/fnl_vs_direct/dry_run_out``
which is **not** tracked in git; the directory is created on demand.

CLI::

    python -m experiments.fnl_vs_direct.latex_bulk_dry_run \\
        [--out-dir PATH] [--limit N] [--corpus nichtlinear|bernstein|both] \\
        [--fail-snippet SPEC ...]

Determinism: identical invocation -> byte-identical ``stats.jsonl``. No
wall-clock values, no UUIDs, no PRNG -- snippet order is sorted by
(corpus, snippet_id) and event payloads are pure functions of inputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# Make sure the in-repo src/ wins over any editable install when this is run
# as a script (``python -m experiments.fnl_vs_direct.latex_bulk_dry_run``).
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from pyirk.authoring.latex import find_snippet, parse_snippets  # noqa: E402

from experiments.fnl_vs_direct.metrics import (  # noqa: E402
    aggregate_events,
    summarize_by_corpus,
)


SELECTION_FILE = _THIS_DIR / "snippet_selection.json"
DEFAULT_OUT_DIR = _THIS_DIR / "dry_run_out"

CORPUS_TEX: Dict[str, Path] = {
    "nichtlinear": _THIS_DIR / "corpus_gold__gitignore__" / "nichtlinear" / "kapitel2.tex",
    "bernstein": _THIS_DIR / "corpus_gold__gitignore__" / "bernstein" / "chunk_full_source.tex",
}

# One default fail-snippet per corpus so the aggregator always sees a
# validation_fail event in the default run; chosen as the smallest sorted ID
# in the selection so it is also hit by smallish --limit values in tests.
DEFAULT_FAIL_SNIPPETS: Dict[str, Set[str]] = {
    "nichtlinear": {"2"},
    "bernstein": {"1"},
}


# Per-type code-stub templates. The strings are illustrative payloads only;
# nothing in this harness actually validates them. ``{label}`` is filled in
# per snippet so the output is uniquely identifiable.
_OK_STUB_TEMPLATES: Dict[str, str] = {
    "notation": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label}",\n'
        '    R2__has_description="mock dry-run import (notation)",\n'
        ')\n'
        'I8001.set_relation(p.R24["has LaTeX representation"], "$arg1$")\n'
    ),
    "subclass": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label}",\n'
        '    R3__is_subclass_of=p.I1["general item"],\n'
        ')\n'
    ),
    "instance": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label}",\n'
        '    R4__is_instance_of=p.I1["general item"],\n'
        ')\n'
    ),
    "declaration": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label}",\n'
        '    R2__has_description="mock dry-run import (declaration)",\n'
        ')\n'
    ),
    "equivalence": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label} equivalence",\n'
        '    R2__has_description="mock dry-run import (equivalence)",\n'
        ')\n'
    ),
    "qualified": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label} qualified",\n'
        '    R2__has_description="mock dry-run import (qualified)",\n'
        ')\n'
    ),
    "definition_and": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label} def_and",\n'
        '    R2__has_description="mock dry-run import (definition_and)",\n'
        ')\n'
    ),
    "definition_or": (
        'I8001 = p.create_item(\n'
        '    R1__has_label="mock {label} def_or",\n'
        '    R2__has_description="mock dry-run import (definition_or)",\n'
        ')\n'
    ),
}

_DEFAULT_STUB = (
    'I8001 = p.create_item(\n'
    '    R1__has_label="mock {label}",\n'
    '    R2__has_description="mock dry-run import",\n'
    ')\n'
)


class MockClaude:
    """Deterministic stand-in for the LLM-driven proposal step.

    ``propose(corpus, snippet_id, snippet_type, snippet_text)`` returns a
    full per-snippet event-record dict. The shape (keys, event vocabulary,
    outcome string) mirrors what
    :func:`pyirk.authoring.import_one_statement` would produce, but no LLM
    is invoked and no Python is executed.

    State is parameterised entirely by the constructor; ``propose`` itself
    is a pure function of its arguments.
    """

    def __init__(self, fail_snippet_ids_by_corpus: Optional[Dict[str, Set[str]]] = None):
        self.fail_by_corpus: Dict[str, Set[str]] = {
            c: set(s) for c, s in (fail_snippet_ids_by_corpus or {}).items()
        }

    def propose(
        self,
        corpus: str,
        snippet_id: str,
        snippet_type: str,
        snippet_text: str,
    ) -> dict:
        stub_template = _OK_STUB_TEMPLATES.get(snippet_type, _DEFAULT_STUB)
        label = f"{corpus}_{snippet_id}_{snippet_type}"
        code = stub_template.format(label=label)
        events: List[dict] = []
        should_fail = snippet_id in self.fail_by_corpus.get(corpus, set())
        if should_fail:
            # exercise the validation_fail -> retry -> ok path
            events.append(
                {
                    "event": "validation_fail",
                    "attempt": 1,
                    "error": "mock injected: simulated round-trip failure",
                }
            )
            events.append({"event": "ok", "attempt": 2})
            outcome = "ok"
        else:
            events.append({"event": "ok", "attempt": 1})
            outcome = "ok"
        return {
            "snippet_id": snippet_id,
            "corpus": corpus,
            "type": snippet_type,
            "outcome": outcome,
            "events": events,
            "code": code,
            "snippet_text_length": len(snippet_text),
            "fnl_excerpt_present": False,
        }


def load_selection(path: Path = SELECTION_FILE) -> dict:
    with path.open() as fp:
        return json.load(fp)


_SID_NUM_RE = re.compile(r"^(\d+)(.*)$")


def _snippet_sort_key(snippet_id: str) -> tuple:
    """Natural sort: numeric prefix first, then any alphabetic suffix.

    Ensures ``"2" < "10"`` and ``"17" < "17i"`` deterministically.
    """
    m = _SID_NUM_RE.match(snippet_id)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, snippet_id)


def _parse_fail_specs(specs: List[str]) -> Dict[str, Set[str]]:
    """Parse ``--fail-snippet`` CLI specs.

    Each spec is either ``CORPUS:ID`` (apply only to that corpus) or a bare
    ``ID`` (apply to all corpora).
    """
    out: Dict[str, Set[str]] = {c: set() for c in CORPUS_TEX}
    for spec in specs:
        if ":" in spec:
            corpus, sid = spec.split(":", 1)
            out.setdefault(corpus, set()).add(sid)
        else:
            for c in out:
                out[c].add(spec)
    return out


def build_records(
    selection: dict,
    corpora: List[str],
    limit: int,
    fail_map: Dict[str, Set[str]],
) -> List[dict]:
    """Pure (modulo file reads) record-builder.

    Reads the .tex files from ``CORPUS_TEX[corpus]`` and segments them via
    :func:`parse_snippets`; for each selected snippet, asks the mock for an
    event-record. Records are sorted by (corpus, snippet_id) on the way out
    so the JSONL is byte-deterministic across runs.
    """
    mock = MockClaude(fail_snippet_ids_by_corpus=fail_map)
    records: List[dict] = []
    for corpus in corpora:
        tex_path = CORPUS_TEX.get(corpus)
        if tex_path is None or not tex_path.exists():
            print(
                f"WARN: corpus tex not available for {corpus!r} ({tex_path}); skipping",
                file=sys.stderr,
            )
            continue
        snippets = parse_snippets(tex_path.read_text())
        selected = list(selection["corpora"].get(corpus, []))
        # deterministic natural sort by snippet_id (numeric prefix), stable across runs
        selected_sorted = sorted(selected, key=lambda e: _snippet_sort_key(e["snippet_id"]))
        if limit and limit > 0:
            selected_sorted = selected_sorted[:limit]
        for entry in selected_sorted:
            sid = entry["snippet_id"]
            stype = entry.get("type", "unknown")
            snip = find_snippet(snippets, sid)
            if snip is None:
                rec = {
                    "snippet_id": sid,
                    "corpus": corpus,
                    "type": stype,
                    "outcome": "missing",
                    "events": [{"event": "missing"}],
                    "code": "",
                    "snippet_text_length": 0,
                    "fnl_excerpt_present": False,
                }
            else:
                rec = mock.propose(corpus, sid, stype, snip.text)
            records.append(rec)
    records.sort(key=lambda r: (r["corpus"], _snippet_sort_key(r["snippet_id"])))
    return records


def write_outputs(records: List[dict], selection: dict, out_dir: Path, corpora: List[str]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats_path = out_dir / "stats.jsonl"
    summary_path = out_dir / "summary.json"
    with stats_path.open("w") as fp:
        for r in records:
            fp.write(json.dumps(r, sort_keys=True) + "\n")
    summary = {
        "n_records": len(records),
        "corpora_processed": list(corpora),
        "aggregate": aggregate_events(records),
        "by_corpus": summarize_by_corpus(records, selection),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="if > 0, process at most N selected snippets per corpus",
    )
    ap.add_argument(
        "--corpus",
        choices=["nichtlinear", "bernstein", "both"],
        default="both",
    )
    ap.add_argument(
        "--fail-snippet",
        action="append",
        default=[],
        metavar="SPEC",
        help="inject a validation_fail-then-ok path for SPEC (either 'ID' for "
        "all corpora or 'CORPUS:ID'); repeatable",
    )
    return ap.parse_args(argv)


def main(argv=None) -> int:
    cli = parse_args(argv)
    selection = load_selection()
    fail_map: Dict[str, Set[str]] = {c: set(ids) for c, ids in DEFAULT_FAIL_SNIPPETS.items()}
    extra_fail = _parse_fail_specs(list(cli.fail_snippet))
    for c, ids in extra_fail.items():
        fail_map.setdefault(c, set()).update(ids)
    corpora = ["nichtlinear", "bernstein"] if cli.corpus == "both" else [cli.corpus]

    records = build_records(selection, corpora, cli.limit, fail_map)
    summary = write_outputs(records, selection, cli.out_dir, corpora)

    agg = summary["aggregate"]
    print(
        f"FNLVSDIRECT-DRYRUN: n={agg['n_snippets']} "
        f"validity_rate={agg['validity_rate']:.3f} "
        f"retry_rate={agg['retry_rate']:.3f} "
        f"fork_rate={agg['fork_rate']:.3f} "
        f"out_dir={cli.out_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
