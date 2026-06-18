"""Aggregate the fnl_vs_direct experiment artefacts into report tables.

Reads four input sources:

* ``stats.jsonl``           -- per-snippet direct-arm outcomes + cost.
* ``structural_diff.json``  -- per-snippet structural diff (corpus A).
* ``judge_results.jsonl``   -- per-snippet LLM-judge verdicts.
* ``snippet_selection.json`` -- statement-type tags per snippet.

Writes three artefacts:

* ``aggregate.json`` -- per-snippet records + grouped aggregations
  (by type, by corpus, plus a calibration block that compares the
  structural diff to the LLM judge on corpus A).
* ``aggregate.md`` -- human-readable tables (per type, per corpus) plus
  the calibration section.
* ``spotcheck.md`` -- 8-10 type-mixed snippets for human review.
  Selection prioritises judge-vs-structural divergence on corpus A and
  low judge confidence on corpus B, while guaranteeing coverage of the
  mandated statement types.

Pure aggregation functions live above ``main`` and are imported by the
test suite directly; the CLI is a thin orchestrator.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


# Required statement types in spotcheck; one of definition_and/definition_or
# satisfies the "definition" requirement.
REQUIRED_TYPES = [
    "declaration",
    "equivalence",
    "instance",
    "notation",
    "qualified",
    "subclass",
]
DEFINITION_TYPE_GROUP = {"definition_and", "definition_or"}


_SID_NUM_RE = re.compile(r"^(\d+)(.*)$")


def _snippet_sort_key(snippet_id: str) -> tuple:
    m = _SID_NUM_RE.match(snippet_id)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, snippet_id)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_stats(path: Path) -> Dict[Tuple[str, str], dict]:
    """Index ``stats.jsonl`` records by (corpus, snippet_id)."""
    out: Dict[Tuple[str, str], dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        key = (str(rec["corpus"]), str(rec["snippet_id"]))
        out[key] = rec
    return out


def load_judge(path: Path) -> Dict[Tuple[str, str], dict]:
    """Index ``judge_results.jsonl`` records by (corpus, snippet_id).

    Last-write-wins so re-judged snippets are honoured.
    """
    out: Dict[Tuple[str, str], dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        key = (str(rec["corpus"]), str(rec["snippet_id"]))
        out[key] = rec
    return out


def load_structural_diff(path: Path) -> Dict[str, dict]:
    """Return the diffs-by-snippet-id mapping (corpus A only)."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    diffs = payload.get("diffs", {})
    return {str(k): v for k, v in diffs.items()}


def load_selection(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Per-snippet record construction
# ---------------------------------------------------------------------------


def _structural_clean(diff_entry: Optional[dict]) -> Optional[bool]:
    """Return whether the structural diff for a snippet is empty.

    ``None`` if the snippet is not in the structural diff (e.g. corpus B).
    """
    if diff_entry is None:
        return None
    return (
        not diff_entry.get("missing_items")
        and not diff_entry.get("extra_items")
        and not diff_entry.get("mismatched_relations")
        and not diff_entry.get("missing_relations")
        and not diff_entry.get("extra_relations")
    )


def _attempts_and_cost(stats_rec: Optional[dict]) -> Tuple[int, float]:
    if stats_rec is None:
        return (0, 0.0)
    events = stats_rec.get("events", []) or []
    attempts = 0
    cost = 0.0
    for ev in events:
        a = ev.get("attempt")
        if isinstance(a, int) and a > attempts:
            attempts = a
        c = ev.get("cost_usd")
        if isinstance(c, (int, float)):
            cost += float(c)
    if attempts == 0 and events:
        attempts = len(events)
    return attempts, cost


def build_records(
    *,
    selection: dict,
    stats: Dict[Tuple[str, str], dict],
    judge: Dict[Tuple[str, str], dict],
    struct_diff: Dict[str, dict],
    structural_corpus: str = "nichtlinear",
) -> List[dict]:
    """Return one record per (corpus, snippet) entry in the selection."""
    records: List[dict] = []
    for corpus, entries in selection.get("corpora", {}).items():
        for entry in entries:
            sid = str(entry["snippet_id"])
            stype = str(entry.get("type", ""))
            stats_rec = stats.get((corpus, sid))
            judge_rec = judge.get((corpus, sid))
            diff_entry = (
                struct_diff.get(sid) if corpus == structural_corpus else None
            )
            structural_diff_empty = _structural_clean(diff_entry)
            attempts, cost_usd = _attempts_and_cost(stats_rec)
            records.append(
                {
                    "corpus": corpus,
                    "snippet_id": sid,
                    "type": stype,
                    "valid": bool(stats_rec.get("ok")) if stats_rec else False,
                    "structural_diff_empty": structural_diff_empty,
                    "judge_verdict": (judge_rec or {}).get("verdict"),
                    "judge_confidence": (judge_rec or {}).get("confidence"),
                    "judge_reason": (judge_rec or {}).get("reason"),
                    "attempts": attempts,
                    "cost_usd": cost_usd,
                }
            )
    records.sort(key=lambda r: (r["corpus"], _snippet_sort_key(r["snippet_id"])))
    return records


# ---------------------------------------------------------------------------
# Grouped aggregations
# ---------------------------------------------------------------------------


def _empty_verdict_counter() -> Dict[str, int]:
    return {"equivalent": 0, "partial": 0, "wrong": 0}


def _group_by(records: List[dict], key: str) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = defaultdict(list)
    for r in records:
        out[r[key]].append(r)
    return dict(out)


def aggregate_group(records: List[dict]) -> dict:
    """Compute aggregate stats for a single group (type, corpus, etc.)."""
    n = len(records)
    n_valid = sum(1 for r in records if r["valid"])
    n_structural_clean = sum(
        1 for r in records if r.get("structural_diff_empty") is True
    )
    n_struct_applicable = sum(
        1 for r in records if r.get("structural_diff_empty") is not None
    )
    verdicts = _empty_verdict_counter()
    for r in records:
        v = r.get("judge_verdict")
        if v in verdicts:
            verdicts[v] += 1
    cost_total = sum(r.get("cost_usd", 0.0) or 0.0 for r in records)
    mean_cost = cost_total / n if n else 0.0
    return {
        "n": n,
        "n_valid": n_valid,
        "n_structural_clean": n_structural_clean,
        "n_structural_applicable": n_struct_applicable,
        "judge_verdicts": verdicts,
        "mean_cost_usd": mean_cost,
    }


def calibration(records: List[dict], structural_corpus: str = "nichtlinear") -> dict:
    """Compare structural diff vs judge verdict on the corpus-with-diff.

    Agreement rule: ``structural_clean == True`` <-> judge_verdict == ``equivalent``.
    Anything else counts as divergence (including missing judge verdicts).
    """
    pool = [
        r
        for r in records
        if r["corpus"] == structural_corpus and r["structural_diff_empty"] is not None
    ]
    n = len(pool)
    n_agreement = 0
    divergences: List[dict] = []
    for r in pool:
        clean = r["structural_diff_empty"]
        verdict = r.get("judge_verdict")
        equiv = verdict == "equivalent"
        if clean == equiv:
            n_agreement += 1
        else:
            if clean and not equiv:
                note = "structural empty but judge not equivalent"
            elif equiv and not clean:
                note = "judge equivalent but structural diff nonzero"
            else:
                note = "mismatch"
            divergences.append(
                {
                    "snippet_id": r["snippet_id"],
                    "structural_clean": clean,
                    "judge_verdict": verdict,
                    "note": note,
                }
            )
    divergences.sort(key=lambda d: _snippet_sort_key(d["snippet_id"]))
    return {
        "n_corpus_A": n,
        "n_agreement": n_agreement,
        "n_divergence": len(divergences),
        "divergence_list": divergences,
    }


def build_aggregate(
    records: List[dict],
    structural_corpus: str = "nichtlinear",
) -> dict:
    by_type = {
        t: aggregate_group(group) for t, group in _group_by(records, "type").items()
    }
    by_corpus = {
        c: aggregate_group(group) for c, group in _group_by(records, "corpus").items()
    }
    return {
        "records": records,
        "by_type": by_type,
        "by_corpus": by_corpus,
        "calibration": calibration(records, structural_corpus=structural_corpus),
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "n/a"
    return f"{100.0 * num / denom:.1f}%"


def _format_money(x: float) -> str:
    return f"${x:.4f}"


def render_aggregate_md(aggregate: dict) -> str:
    lines: List[str] = []
    lines.append("# fnl_vs_direct -- aggregate")
    lines.append("")
    lines.append("## Per Statement Type")
    lines.append("")
    lines.append(
        "| type | n | valid % | structural clean % (A) | judge equivalent | judge partial | judge wrong | mean cost $ |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for stype in sorted(aggregate["by_type"].keys()):
        g = aggregate["by_type"][stype]
        struct_pct = (
            _pct(g["n_structural_clean"], g["n_structural_applicable"])
            if g["n_structural_applicable"]
            else "-"
        )
        lines.append(
            f"| {stype} | {g['n']} | {_pct(g['n_valid'], g['n'])} | "
            f"{struct_pct} | {g['judge_verdicts']['equivalent']} | "
            f"{g['judge_verdicts']['partial']} | {g['judge_verdicts']['wrong']} | "
            f"{_format_money(g['mean_cost_usd'])} |"
        )
    lines.append("")

    lines.append("## Per Corpus Summary")
    lines.append("")
    lines.append(
        "| corpus | n | valid % | structural clean % | judge equivalent | judge partial | judge wrong | mean cost $ |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for corpus in sorted(aggregate["by_corpus"].keys()):
        g = aggregate["by_corpus"][corpus]
        struct_pct = (
            _pct(g["n_structural_clean"], g["n_structural_applicable"])
            if g["n_structural_applicable"]
            else "-"
        )
        lines.append(
            f"| {corpus} | {g['n']} | {_pct(g['n_valid'], g['n'])} | "
            f"{struct_pct} | {g['judge_verdicts']['equivalent']} | "
            f"{g['judge_verdicts']['partial']} | {g['judge_verdicts']['wrong']} | "
            f"{_format_money(g['mean_cost_usd'])} |"
        )
    lines.append("")

    cal = aggregate["calibration"]
    lines.append("## Calibration Judge <-> Structural Diff (Korpus A)")
    lines.append("")
    lines.append(
        f"- Agreement: {cal['n_agreement']}/{cal['n_corpus_A']} "
        f"({_pct(cal['n_agreement'], cal['n_corpus_A'])})"
    )
    lines.append(f"- Divergences: {cal['n_divergence']}")
    lines.append("")
    if cal["divergence_list"]:
        lines.append(
            "| snippet | structural_clean | judge_verdict | note |"
        )
        lines.append("|---|---|---|---|")
        for d in cal["divergence_list"]:
            lines.append(
                f"| {d['snippet_id']} | {d['structural_clean']} | "
                f"{d['judge_verdict']} | {d['note']} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Spotcheck selection
# ---------------------------------------------------------------------------


def _priority_score(rec: dict, structural_corpus: str) -> float:
    """Higher = more interesting for human review."""
    if rec["corpus"] == structural_corpus and rec["structural_diff_empty"] is not None:
        clean = rec["structural_diff_empty"]
        equiv = rec.get("judge_verdict") == "equivalent"
        return 1.0 if clean != equiv else 0.1
    # corpus B (or no structural): low judge confidence is interesting.
    conf = rec.get("judge_confidence")
    if isinstance(conf, (int, float)):
        return 1.0 - float(conf)
    return 0.5


def select_spotcheck(
    records: List[dict],
    *,
    structural_corpus: str = "nichtlinear",
    target_count: int = 10,
    min_per_corpus: int = 3,
) -> List[dict]:
    """Choose 8-10 records for human spotcheck review.

    Guarantees:
    * each entry in :data:`REQUIRED_TYPES` is represented if available;
    * at least one record from :data:`DEFINITION_TYPE_GROUP` is included
      if available;
    * at least ``min_per_corpus`` records from each corpus represented in
      the input;
    * total size is at most ``target_count`` and at least 8 when the input
      can support it.

    Selection within constraints is by descending priority score (judge vs
    structural divergence on corpus A, low judge confidence on corpus B).
    """
    pool = list(records)
    pool.sort(
        key=lambda r: (
            -_priority_score(r, structural_corpus),
            r["corpus"],
            _snippet_sort_key(r["snippet_id"]),
        )
    )
    selected: List[dict] = []
    selected_keys: set = set()

    def add(rec):
        key = (rec["corpus"], rec["snippet_id"])
        if key in selected_keys:
            return False
        selected.append(rec)
        selected_keys.add(key)
        return True

    # Required statement types -- first available per type, by priority.
    for stype in REQUIRED_TYPES:
        for rec in pool:
            if rec["type"] == stype:
                add(rec)
                break

    # Definition group: one of definition_and / definition_or, if present.
    if not any(r["type"] in DEFINITION_TYPE_GROUP for r in selected):
        for rec in pool:
            if rec["type"] in DEFINITION_TYPE_GROUP:
                add(rec)
                break

    # Min-per-corpus.  Pad the underrepresented corpus first with high-priority
    # picks that are not yet selected.
    corpora_present = sorted({r["corpus"] for r in pool})
    for corpus in corpora_present:
        deficit = min_per_corpus - sum(1 for r in selected if r["corpus"] == corpus)
        if deficit <= 0:
            continue
        for rec in pool:
            if deficit <= 0:
                break
            if rec["corpus"] != corpus:
                continue
            if add(rec):
                deficit -= 1

    # Fill remaining slots with highest-priority unselected records.
    for rec in pool:
        if len(selected) >= target_count:
            break
        add(rec)

    # Final stable order: by corpus, then snippet id.
    selected.sort(key=lambda r: (r["corpus"], _snippet_sort_key(r["snippet_id"])))
    return selected


# ---------------------------------------------------------------------------
# Spotcheck markdown rendering
# ---------------------------------------------------------------------------


def _safe_block(label: str, content: Optional[str], lang: str = "") -> List[str]:
    if not content:
        return [f"**{label}:** *(unavailable)*", ""]
    fence = f"```{lang}".rstrip()
    return [f"**{label}:**", fence, content.rstrip(), "```", ""]


def render_spotcheck_md(
    selected: List[dict],
    *,
    latex_sources: Dict[str, str],
    fnl_sources: Dict[str, str],
    direct_sources: Dict[str, str],
    struct_diff: Dict[str, dict],
    structural_corpus: str = "nichtlinear",
) -> str:
    """Render a spotcheck document.

    ``latex_sources``/``fnl_sources``/``direct_sources`` are corpus-keyed
    raw module contents (one string per corpus); per-snippet slices are
    cut out on the fly via :mod:`judge_harness`'s extractors.
    """
    from experiments.fnl_vs_direct.judge_harness import (
        extract_fnl_snippet_block,
        extract_latex_snippet_block,
        extract_pyirk_snippet_block,
    )

    lines: List[str] = ["# fnl_vs_direct -- spotcheck", ""]
    for rec in selected:
        corpus = rec["corpus"]
        sid = rec["snippet_id"]
        lines.append(f"## Snippet {corpus}/{sid}  (type: {rec['type']})")
        lines.append("")

        latex = extract_latex_snippet_block(latex_sources.get(corpus, ""), sid)
        fnl = extract_fnl_snippet_block(fnl_sources.get(corpus, ""), sid)
        direct = extract_pyirk_snippet_block(direct_sources.get(corpus, ""), sid)

        lines.extend(_safe_block("LaTeX source", latex, lang="latex"))
        lines.extend(_safe_block("FNL gold", fnl, lang=""))
        lines.extend(_safe_block("Direct pyirk", direct, lang="python"))

        if corpus == structural_corpus:
            diff_entry = struct_diff.get(sid)
            if diff_entry is not None:
                lines.append("**Structural diff:**")
                lines.append("```json")
                lines.append(json.dumps(diff_entry, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")

        verdict = rec.get("judge_verdict") or "n/a"
        conf = rec.get("judge_confidence")
        conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"
        lines.append(f"**Judge verdict:** `{verdict}` (confidence: {conf_str})")
        reason = rec.get("judge_reason") or ""
        if reason:
            lines.append("")
            lines.append(f"> {reason}")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _read_or_empty(path: Optional[Path]) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stats", required=True, type=Path)
    ap.add_argument("--structural-diff", required=True, type=Path)
    ap.add_argument("--judge", required=True, type=Path)
    ap.add_argument("--selection", required=True, type=Path)
    ap.add_argument("--out-json", required=True, type=Path)
    ap.add_argument("--out-md", required=True, type=Path)
    ap.add_argument("--out-spotcheck", required=True, type=Path)
    ap.add_argument(
        "--structural-corpus",
        default="nichtlinear",
        help="corpus with which the structural diff is associated",
    )
    ap.add_argument(
        "--latex-nichtlinear",
        type=Path,
        default=Path(
            "experiments/fnl_vs_direct/corpus_gold__gitignore__/nichtlinear/kapitel2.tex"
        ),
    )
    ap.add_argument(
        "--latex-bernstein",
        type=Path,
        default=Path(
            "experiments/fnl_vs_direct/corpus_gold__gitignore__/bernstein/chunk_full_source.tex"
        ),
    )
    ap.add_argument(
        "--fnl-nichtlinear",
        type=Path,
        default=Path(
            "experiments/fnl_vs_direct/corpus_gold__gitignore__/nichtlinear/formalized_statements_nl.md"
        ),
    )
    ap.add_argument(
        "--fnl-bernstein",
        type=Path,
        default=Path(
            "experiments/fnl_vs_direct/corpus_gold__gitignore__/bernstein/formalized_statements0.md"
        ),
    )
    ap.add_argument(
        "--direct-nichtlinear",
        type=Path,
        default=Path(
            "experiments/fnl_vs_direct/run_out/nichtlinear/direct_arm.py"
        ),
    )
    ap.add_argument(
        "--direct-bernstein",
        type=Path,
        default=Path(
            "experiments/fnl_vs_direct/run_out/bernstein/direct_arm.py"
        ),
    )
    return ap.parse_args(argv)


def main(argv=None) -> int:
    cli = _parse_args(argv)

    stats = load_stats(cli.stats)
    judge = load_judge(cli.judge)
    struct_diff = load_structural_diff(cli.structural_diff)
    selection = load_selection(cli.selection)

    records = build_records(
        selection=selection,
        stats=stats,
        judge=judge,
        struct_diff=struct_diff,
        structural_corpus=cli.structural_corpus,
    )
    aggregate = build_aggregate(records, structural_corpus=cli.structural_corpus)

    cli.out_json.parent.mkdir(parents=True, exist_ok=True)
    cli.out_json.write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    cli.out_md.write_text(render_aggregate_md(aggregate), encoding="utf-8")

    selected = select_spotcheck(
        records, structural_corpus=cli.structural_corpus, target_count=10
    )

    latex_sources = {
        "nichtlinear": _read_or_empty(cli.latex_nichtlinear),
        "bernstein": _read_or_empty(cli.latex_bernstein),
    }
    fnl_sources = {
        "nichtlinear": _read_or_empty(cli.fnl_nichtlinear),
        "bernstein": _read_or_empty(cli.fnl_bernstein),
    }
    direct_sources = {
        "nichtlinear": _read_or_empty(cli.direct_nichtlinear),
        "bernstein": _read_or_empty(cli.direct_bernstein),
    }

    spotcheck_md = render_spotcheck_md(
        selected,
        latex_sources=latex_sources,
        fnl_sources=fnl_sources,
        direct_sources=direct_sources,
        struct_diff=struct_diff,
        structural_corpus=cli.structural_corpus,
    )
    cli.out_spotcheck.write_text(spotcheck_md, encoding="utf-8")

    print(
        f"AGGREGATE: records={len(records)} "
        f"types={len(aggregate['by_type'])} "
        f"corpora={len(aggregate['by_corpus'])} "
        f"spotcheck={len(selected)} "
        f"out_json={cli.out_json}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
