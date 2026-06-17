"""Deterministic, type-quotaed snippet selection for the FNL-vs-direct experiment.

Pure-Python module without any LLM calls. The selection is reproducible from
the FNL gold sources committed under ``corpus_gold__gitignore__/`` and is
intended to feed the comparison runs (FNL pipeline vs. direct-from-LaTeX)
on a representative, type-mixed subset of each corpus.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CORPUS_ROOT = Path(__file__).parent / "corpus_gold__gitignore__"

CORPUS_FILES: Dict[str, str] = {
    "nichtlinear": "formalized_statements_nl.md",
    "bernstein": "formalized_statements0.md",
}

LIGHT_TYPES = {"declaration", "notation", "instance", "subclass"}
MEDIUM_TYPES = {"equivalence", "qualified"}
HEAVY_TYPES = {"definition_and", "definition_or"}

THRESHOLDS = {
    "validity_min": 0.9,
    "faithfulness": "structural_diff==0 OR judge+spotcheck confirmed",
}

_MARKER_RE = re.compile(r"(?m)^-\s*//\s*snippet\(([A-Za-z0-9]+)\)")


def tag_snippet(snippet_id: str, fnl_text: str) -> str:
    """Deterministic, regex/keyword based statement-type tag.

    Priority (heaviest wins): definition_or > definition_and > equivalence >
    qualified > subclass > instance > notation > declaration.
    Snippets with ``i`` suffix are tagged ``ignored`` regardless of body.
    """
    if snippet_id.endswith("i"):
        return "ignored"
    text = fnl_text
    if re.search(r"(?m)^\s*-\s*OR\b", text):
        return "definition_or"
    if re.search(r"(?m)^\s*-\s*AND\b", text):
        return "definition_and"
    if (
        "equivalence-statement" in text
        or "equivalence statement" in text
        or re.search(r"\bif and only if\b", text, re.IGNORECASE)
        or re.search(r"\biff\b", text)
    ):
        return "equivalence"
    if (
        "qqq" in text
        or "is a qualifier" in text
        or re.search(r"(?m)^\s*-\s*For\s+(all|each|every)\b", text)
    ):
        return "qualified"
    if "is a subclass of" in text or "is a subproperty of" in text:
        return "subclass"
    if "is an instance of" in text or "is instance of" in text:
        return "instance"
    if "associated LaTeX notation" in text or "has notation" in text:
        return "notation"
    return "declaration"


def load_fnl_gold(corpus: str) -> Dict[str, str]:
    """Parse ``// snippet(N)`` markers from a FNL gold file into ``{id: body}``.

    The body is the verbatim text between the end of the marker and the start
    of the next marker (or EOF). The marker must start a bulleted line
    (``- // snippet(...)``) so that ``snippet(...)`` mentions inside comments
    do not produce spurious entries.
    """
    if corpus not in CORPUS_FILES:
        raise KeyError(f"unknown corpus: {corpus!r}")
    path = CORPUS_ROOT / corpus / CORPUS_FILES[corpus]
    text = path.read_text(encoding="utf-8")
    matches = list(_MARKER_RE.finditer(text))
    out: Dict[str, str] = {}
    for i, m in enumerate(matches):
        snippet_id = m.group(1)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[snippet_id] = text[body_start:body_end].strip()
    return out


def _snippet_sort_key(snippet_id: str) -> Tuple[int, str]:
    m = re.match(r"\d+", snippet_id)
    if m is None:
        return (10**9, snippet_id)
    return (int(m.group()), snippet_id)


def _pick_stride(items: List[Tuple[str, str, str]], n: int) -> List[Tuple[str, str, str]]:
    if not items or n <= 0:
        return []
    if n >= len(items):
        return list(items)
    stride = max(1, len(items) // n)
    selected = items[::stride]
    return selected[:n]


def build_selection(
    corpus: str,
    target_size: int = 25,
    seed: int = 0,
    gold: Optional[Dict[str, str]] = None,
) -> List[Dict]:
    """Build a deterministic, type-quotaed selection for one corpus.

    ``seed`` is accepted for interface stability; the function uses no
    randomness so identical inputs always yield identical output. When
    ``gold`` is supplied it is used verbatim; otherwise the on-disk corpus
    is loaded via ``load_fnl_gold``.

    The selection aims at roughly 1/3 light, 1/3 medium, 1/3 heavy types
    (see ``LIGHT_TYPES`` / ``MEDIUM_TYPES`` / ``HEAVY_TYPES``). If a bucket
    has fewer items than its quota, the remainder is redistributed to the
    other buckets (light -> medium -> heavy). The final list is clamped to
    at most 30 items and sorted by snippet_id.
    """
    if gold is None:
        gold = load_fnl_gold(corpus)

    tagged: List[Tuple[str, str, str]] = []
    for snippet_id, body in gold.items():
        t = tag_snippet(snippet_id, body)
        if t == "ignored":
            continue
        tagged.append((snippet_id, t, body))

    buckets: Dict[str, List[Tuple[str, str, str]]] = {
        "light": [],
        "medium": [],
        "heavy": [],
    }
    for item in tagged:
        t = item[1]
        if t in LIGHT_TYPES:
            buckets["light"].append(item)
        elif t in MEDIUM_TYPES:
            buckets["medium"].append(item)
        elif t in HEAVY_TYPES:
            buckets["heavy"].append(item)
    for k in buckets:
        buckets[k].sort(key=lambda x: _snippet_sort_key(x[0]))

    base_light = target_size // 3
    base_medium = target_size // 3
    base_heavy = target_size - base_light - base_medium

    take_light = min(base_light, len(buckets["light"]))
    take_medium = min(base_medium, len(buckets["medium"]))
    take_heavy = min(base_heavy, len(buckets["heavy"]))

    remaining = target_size - take_light - take_medium - take_heavy
    for bucket_name in ("light", "medium", "heavy"):
        if remaining <= 0:
            break
        current = {"light": take_light, "medium": take_medium, "heavy": take_heavy}[bucket_name]
        avail = len(buckets[bucket_name]) - current
        add = min(remaining, avail)
        if bucket_name == "light":
            take_light += add
        elif bucket_name == "medium":
            take_medium += add
        else:
            take_heavy += add
        remaining -= add

    selected: List[Tuple[str, str, str]] = []
    selected.extend(_pick_stride(buckets["light"], take_light))
    selected.extend(_pick_stride(buckets["medium"], take_medium))
    selected.extend(_pick_stride(buckets["heavy"], take_heavy))

    selected.sort(key=lambda x: _snippet_sort_key(x[0]))
    if len(selected) > 30:
        selected = selected[:30]

    return [
        {"snippet_id": sid, "type": t, "fnl_excerpt": body[:200]}
        for (sid, t, body) in selected
    ]


def build_selection_json(seed: int = 0) -> Dict:
    corpora = {}
    for corpus in sorted(CORPUS_FILES.keys()):
        corpora[corpus] = build_selection(corpus, seed=seed)
    return {
        "version": 1,
        "seed": seed,
        "thresholds": THRESHOLDS,
        "corpora": corpora,
    }


def main() -> None:
    data = build_selection_json()
    out_path = Path(__file__).parent / "snippet_selection.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for corpus, items in data["corpora"].items():
        type_counts: Dict[str, int] = {}
        for it in items:
            type_counts[it["type"]] = type_counts.get(it["type"], 0) + 1
        print(f"{corpus}: {len(items)} snippets, types={type_counts}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
